"""Clients for the cooking / food sources.

  * TheMealDB       — recipes        (www.themealdb.com)
  * TheCocktailDB   — drinks         (www.thecocktaildb.com)
  * Open Food Facts — product/barcode (world.openfoodfacts.org)

All free (TheMealDB/TheCocktailDB use the public test key ``1`` embedded in
the path), read-only, and host-pinned via the shared
:class:`~tools.http_client.PublicApiClient`. Methods raise
:class:`~tools.http_client.HttpClientError` on failure.
"""

from __future__ import annotations

from typing import Any, Optional

from tools.http_client import PublicApiClient

MEALDB_HOST = "www.themealdb.com"
COCKTAILDB_HOST = "www.thecocktaildb.com"
OFF_HOST = "world.openfoodfacts.org"
ALLOWED_HOSTS = (MEALDB_HOST, COCKTAILDB_HOST, OFF_HOST)

# Public developer/test key documented for free use.
MEALDB_BASE = f"https://{MEALDB_HOST}/api/json/v1/1"
COCKTAILDB_BASE = f"https://{COCKTAILDB_HOST}/api/json/v1/1"


class CookingClient:
    def __init__(self, http: Optional[PublicApiClient] = None) -> None:
        self._http = http or PublicApiClient(allowed_hosts=ALLOWED_HOSTS)

    def recipe_search(self, query: str) -> Any:
        return self._http.get_json(f"{MEALDB_BASE}/search.php", params={"s": query})

    def recipe_lookup(self, meal_id: str) -> Any:
        return self._http.get_json(f"{MEALDB_BASE}/lookup.php", params={"i": meal_id})

    def cocktail_search(self, query: str) -> Any:
        return self._http.get_json(f"{COCKTAILDB_BASE}/search.php", params={"s": query})

    def food_product(self, barcode: str) -> Any:
        return self._http.get_json(f"https://{OFF_HOST}/api/v2/product/{barcode}.json")
