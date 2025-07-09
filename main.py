from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
import requests
from scrapy import Selector
import json
import time
import urllib3

urllib3.disable_warnings()

app = FastAPI()

class ScrapeRequest(BaseModel):
    url: HttpUrl
    max_retries: int = 5
    delay_between_retries: int = 5  # seconds


@app.post("/scrape")
def scrape_leboncoin(data: ScrapeRequest):
    url = str(data.url)

    proxies = {
        scheme: "http://d57d54756b874e22a4ffa3f4a25d64b9:@api.zyte.com:8011"
        for scheme in ("http", "https")
    }

    headers = {
        "Zyte-Browser-Html": "true",
        "User-Agent": "Mozilla/5.0"
    }

    attempt = 0
    while attempt < data.max_retries:
        try:
            res = requests.get(
                url,
                headers=headers,
                proxies=proxies,
                verify=False,
                timeout=90
            )

            if res.status_code == 200:
                selector = Selector(text=res.text)
                json_data = selector.xpath('//script[@id="__NEXT_DATA__"]/text()').get()

                if not json_data:
                    raise ValueError("Missing __NEXT_DATA__ script tag")

                detailed_data = json.loads(json_data)
                ad = detailed_data.get('props', {}).get('pageProps', {}).get('ad', {})

                # Extract basic fields
                title = ad.get("subject", "").strip()
                description = ad.get("body", "").strip()
                price = (
                    ad.get("price", [None])[0]
                    if isinstance(ad.get("price", []), list)
                    else ad.get("price", None)
                )
                images = ad.get('images', {}).get('urls', [])

                # Extract detailed attributes
                energy_class = ""
                rooms = ""
                surface_area = ""

                for attr in ad.get("attributes", []):
                    key = attr.get("key", "")
                    value = attr.get("value_label", "")
                    if key == "energy_rate":
                        energy_class = value
                    elif key == "rooms":
                        rooms = value
                    elif key == "square":
                        surface_area = value

                # Final JSON structure
                result = {
                    "title": title,
                    "price": price,
                    "description": description,
                    "property_details": {
                        "rooms": rooms,
                        "surface_area": surface_area
                    },
                    "energy_class": energy_class,
                    "images": images
                }

                return result

            else:
                print(f"[Attempt {attempt+1}] HTTP {res.status_code} — retrying in {data.delay_between_retries}s")

        except Exception as e:
            print(f"[Attempt {attempt+1}] Error: {e} — retrying in {data.delay_between_retries}s")

        attempt += 1
        time.sleep(data.delay_between_retries)

    raise HTTPException(status_code=504, detail="Max retries reached. Failed to fetch data.")
