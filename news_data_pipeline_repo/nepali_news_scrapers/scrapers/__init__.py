# from .ekantipur.ekantipur_listings import EkantipurCategoryScraper

from .gorkhapatra.gorkhapatra import GorkhaPatraScraper
from .sharesansar.sharesansar import ShareSansarScraper
from .the_kathmandu_post.the_kathmandu_post import KathmanduPostScraper
from .setopati.setopati import SetoPatiScraper
from .myrepublica.myrepublica import MyRepublicaScraper
from .the_annapurna_post.the_annapurna_post import TheAnnapurnaPostScraper
from .nepalipaisa.nepalipaisa import NepaliPaisaScraper
from .mero_lagani.mero_lagani import MeroLaganiScraper
from .nepali_times.nepali_times import NepaliTimesScraper
from .ekantipur.ekanitpur import EkantipurScraper
from .insta_scraper.ronb_scraper import InstagramScraper
from .icra_scraper.icra_scraper import IcraScraper
from .nepal_rastra_bank.nrb_scraper import NRBScraper
try:
    from .nepse.nepse_securities import NepalStockScraper
except Exception:
    NepalStockScraper = None

# register scrapers here
scrapers = {
    "gorkhapatra": GorkhaPatraScraper,
    "sharesansar": ShareSansarScraper,
    "kathmandupost": KathmanduPostScraper,
    "setopati": SetoPatiScraper,
    "republica": MyRepublicaScraper,
    "annapurna": TheAnnapurnaPostScraper,
    "nepalipaisa": NepaliPaisaScraper,
    "merolagani": MeroLaganiScraper,
    "nepalitimes": NepaliTimesScraper,
    "kantipur": EkantipurScraper,
    "instagram": InstagramScraper,
    "icra": IcraScraper,
    "nrb": NRBScraper,
    "nepse": NepalStockScraper,
    # ...
}
