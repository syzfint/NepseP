
import json
import logging
from .llm.factory import get_llm_provider
from .db_service import DbService

logging.basicConfig(level=logging.INFO)

def generate_embedding(file_name: str, file_data: bytes):
    llm = get_llm_provider()
    db_service = DbService()

    try:
        data_json = json.loads(file_data.decode('utf-8'))

        # Extract metadata fields
        url = data_json.get("url", "")
        title = data_json.get("title", "")
        category = data_json.get("category", "")
        author = data_json.get("author", [])
        published_date = data_json.get("published_date", "")
        published_time = data_json.get("published_time", "")
        text_content = data_json.get("content", "")

       

        if not text_content:
            logging.warning(f"Skipping {file_name}, content is empty.")
            return

        # Create Markdown-style content for embedding generation
        markdown_content = (
            f"#{title}\n"
            f"**Published at:** {published_date} {published_time}\n"
            f"## News Body\n{text_content[:500]}...\n"
            f"**Source:** {url}\n"
            f"**Metadata:** Category: {category} | Author(s): {','.join(author)}\n"
        )

        # Generate the embedding
        combined_embedding = llm.embed(markdown_content)

        # Prepare data for insertion
        data = (
    file_name, url, title, category, 
    " ".join(author) if isinstance(author, list) else " ".join(author.split()),
    published_date, published_time, text_content, combined_embedding
)


        # Insert embedding into the database
        db_service.add_embedding(data)
        logging.info(f"Embedding generated and stored for {file_name}")

    except Exception as e:
        logging.error(f"Error processing {file_name}: {e}")
