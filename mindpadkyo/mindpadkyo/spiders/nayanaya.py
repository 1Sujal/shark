import scrapy
import time
import json

class PropertySharkSpider(scrapy.Spider):
    name = "propertyshark_autocomplete"
    city = "Texas City, TX"          # default value
    property_type = "buildings" 
    custom_settings = {
        "USER_AGENT": None,
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy_impersonate.ImpersonateDownloadHandler",
            "https": "scrapy_impersonate.ImpersonateDownloadHandler",
        },
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
    }

    def start_requests(self):
        city_encoded = self.city.replace(" ", "%20").replace(",", "%2C")
        autocomplete_url = (
            f"https://www.propertyshark.com/plugin/autocomplete/location.json"
            f"?add_locales=1&current_location=wi&locale=nationwide&product=advanced_search&text={city_encoded}"
        )

        yield scrapy.Request(
            autocomplete_url,
            meta={"impersonate": "chrome110"},
            callback=self.parse_autocomplete,
        )

    def parse_autocomplete(self, response):
        data = response.json()
        content = data.get("content", [])
        if not content:
            return

        first = content[0]
        self.location_lcl = first.get("location_lcl")
        self.location_geo_id = first.get("location_geo_id")
        self.location_state = first.get("location_state")
        self.location_name = first.get("location_name")
        self.text_value = first.get("name")

        # Start from page 1
        yield from self.request_properties(response, page=1)

    def request_properties(self, response, page):
        url = f"https://www.propertyshark.com/PS/api/property-search/list/{self.location_lcl}/{self.property_type}"
        payload = {
            "property_type": self.property_type,
            "view": "list",
            "nationwide_location": {
                "location_layer": "micro",
                "text_value": self.text_value,
                "location_name": self.location_name,
                "location_geo_id": self.location_geo_id,
                "location_state": self.location_state,
            },
            "page": page,
        }
        headers = {"Content-Type": "application/json"}

        yield scrapy.Request(
            url,
            method="POST",
            body=json.dumps(payload),
            headers=headers,
            dont_filter=True,
            meta={
                "impersonate": response.meta["impersonate"],
                "impersonate_args": {
                    "verify": False,
                    "timeout": 10,
                },
                "page": page,
            },
            callback=self.parse_properties,
        )

    def parse_properties(self, response):
        data = response.json()
        properties = data.get("properties", [])

        if not properties:
            return  # no more pages

        for prop in properties:
            yield {
                "address": prop.get("address"),
                "building_class": prop.get("building_class_name"),
                "market_value": prop.get("market_value"),
                "square_feet": prop.get("square_feet"),
                "tax_amount": prop.get("tax_amount"),
                "tax_year": prop.get("tax_year"),
                "year_built": prop.get("yr_built"),
                "zip": prop.get("zip"),
                "latitude": prop.get("lat"),
                "longitude": prop.get("lng"),
                "parcel_id": prop.get("parcel_id"),
            }

        # Request next page
        next_page = response.meta["page"] + 1
        yield from self.request_properties(response, next_page)
