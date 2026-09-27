import requests
import xml.etree.ElementTree as ET
from datetime import datetime


SPOTWEB_URL = "http://192.168.1.30:9080/api"
CATEGORY = 7020
LIMIT = 10


def fetch_rss():
    params = {
        "t": "search",
        "cat": CATEGORY,
        "limit": LIMIT,
    }

    response = requests.get(
        SPOTWEB_URL,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    return response.text


def parse_rss(xml_text):
    root = ET.fromstring(xml_text)

    channel = root.find("channel")

    if channel is None:
        raise RuntimeError("RSS bevat geen channel")

    items = channel.findall("item")

    results = []

    for item in items:
        title = item.findtext("title")
        guid = item.findtext("guid")
        pub_date = item.findtext("pubDate")

        enclosure = item.find("enclosure")

        download_url = None
        size = None

        if enclosure is not None:
            download_url = enclosure.get("url")
            size = enclosure.get("length")

        results.append(
            {
                "guid": guid,
                "title": title,
                "pub_date": pub_date,
                "size": int(size) if size else None,
                "download_url": download_url,
            }
        )

    return results


def main():
    print("Fetching Spotweb RSS...")
    print()

    xml_text = fetch_rss()
    results = parse_rss(xml_text)

    print(f"Found {len(results)} results")
    print()

    for result in results:
        print("----------------------------------------")
        print(f"GUID        : {result['guid']}")
        print(f"Title       : {result['title']}")
        print(f"Published   : {result['pub_date']}")

        if result["size"] is not None:
            size_mb = result["size"] / 1024 / 1024
            print(f"Size        : {size_mb:.1f} MB")
        else:
            print("Size        : unknown")

        print(f"Download URL: {result['download_url']}")

    print()
    print("RSS test finished successfully.")


if __name__ == "__main__":
    main()