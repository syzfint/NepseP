from minio import Minio
from minio.error import S3Error
import io
import time
import json
import logging
from dotenv import load_dotenv
import os
from ..embedding_generator import generate_embedding
from ..llm.factory import get_llm_provider
from ..gemini_client import fuzzy_match_company
from ..db_service import DbService
load_dotenv()

logger = logging.getLogger(__name__)



# MinIO Configuration
endpoint = os.getenv("AWS_S3_ENDPOINT")
bucket_name = os.getenv("AWS_BUCKET_NAME")
if endpoint:
    minio_client = Minio(
        endpoint=endpoint,
        access_key=os.getenv("AWS_ACCESS_KEY_ID"),
        secret_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        secure=True #wasabi needs HTTPS 
    )
    logger.info("S3 storage configuration loaded")
else:
    minio_client = None
    logger.warning("AWS_S3_ENDPOINT not set; S3 upload disabled")



def upload_json_to_minio(file_name, json_data):
    llm = get_llm_provider()
    db_service = DbService()

    try:
        url = json_data.get("url", "")
        if db_service.check_if_embeddings_exist(url):
            return False

        if minio_client is None:
            logger.warning("MinIO client not configured; skipping object storage upload")
            return False

        # Upload JSON to MinIO (unchangtreat ned)
        json_bytes = json.dumps(json_data, ensure_ascii=False).encode('utf-8')
        minio_client.put_object(
            bucket_name,
            file_name,
            data=io.BytesIO(json_bytes),
            length=len(json_bytes),
            content_type='application/json'
        )
        logger.info("Uploaded %s to object storage", file_name)

        # Fetch required data
        nepse_companies = db_service.get_all_nepse_companies()
        sector_names = db_service.get_all_sector_names()
        content = json_data.get("content", "")
        event_id = json_data.get("event_id")

        # Extract sectors and companies for ALL scrapers
        affected_sectors, mentioned_companies = llm.extract_companies_and_sectors(
            content, sector_names, nepse_companies
        )

        if "icranepal.com" in url:
            # ICRA-specific: no summary generation
            extraction_content = content[:300]
            summary = "[ICRA Report]"
            impact_score = 0
            relevance_score = 0
        else:
            # Non-ICRA: generate summary and scores
            extraction_content = content
            summary, impact_score, relevance_score = llm.summarize_and_score(
                extraction_content
            )

        # Store in database
        logger.debug("Storing article summary for event_id=%s", event_id)
        article_summary_id = db_service.add_article_summary(
            event_id=event_id,
            url=url,
            summary=summary,
            impact_score=impact_score,
            relevance_score=relevance_score
        )
        if not article_summary_id:
            logger.warning("Failed to store article summary")
            return False

        # Convert sectors and companies to IDs (unchanged)
        sector_ids = [str(db_service.get_sector_id_by_name(sector))
                      for sector in affected_sectors
                      if db_service.get_sector_id_by_name(sector)]
        company_ids = []
        seen_companies = set()
        for company in mentioned_companies:
            company_id = db_service.get_company_id_by_name_or_symbol(company)
            if not company_id:
                fuzzy_match = fuzzy_match_company(company, nepse_companies)
                if fuzzy_match:
                    company_id = db_service.get_company_id_by_name_or_symbol(fuzzy_match)
            if company_id and str(company_id) not in seen_companies:
                seen_companies.add(str(company_id))
                company_ids.append(str(company_id))

        news_impact_id = db_service.add_news_impact(
            event_id=event_id,
            article_summary_id=article_summary_id,
            sector_ids=sector_ids,
            company_ids=company_ids
        )
        if not news_impact_id:
            logger.warning("Failed to create news_impact entry")
            return False

        # Generate embeddings only for non-ICRA scrapers
        if "icranepal.com" not in url:
            generate_embedding(file_name, json_bytes)

        return True

    except S3Error as e:
        logger.error("Failed to upload %s: %s", file_name, e)
    except Exception as e:
        logger.exception("Unexpected error processing %s: %s", file_name, e)
        return False