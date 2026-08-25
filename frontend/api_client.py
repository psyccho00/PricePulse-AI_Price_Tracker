import requests
from typing import List, Dict, Any, Optional

class PriceTrackerAPIClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.token = None

    def _get_headers(self) -> dict:
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    # ==========================================
    # Authentication & User Management Calls
    # ==========================================
    def register(self, name: str, email: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Register a new user.
        """
        try:
            payload = {"name": name, "email": email, "password": password}
            response = requests.post(f"{self.api_url}/auth/register", json=payload, timeout=10)
            if response.status_code == 201:
                return response.json()
            return None
        except Exception as e:
            print(f"Error registering user: {e}")
            return None

    def login(self, email: str, password: str) -> bool:
        """
        Authenticate with email & password and store the token.
        """
        try:
            # FastAPI OAuth2PasswordRequestForm expects URL-encoded form data: username & password
            payload = {"username": email, "password": password}
            response = requests.post(
                f"{self.api_url}/auth/login", 
                data=payload, 
                headers={"Content-Type": "application/x-www-form-urlencoded"}, 
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("access_token")
                return True
            return False
        except Exception as e:
            print(f"Error logging in: {e}")
            return False

    def logout(self):
        """
        Logout user by clearing token.
        """
        self.token = None

    def get_profile(self) -> Optional[Dict[str, Any]]:
        """
        Get the current user's profile.
        """
        try:
            response = requests.get(f"{self.api_url}/auth/me", headers=self._get_headers(), timeout=10)
            if response.status_code == 200:
                return response.json()
            elif response.status_code in (401, 403):
                return {"_auth_error": "unauthorized"}
            return None
        except requests.exceptions.RequestException as e:
            print(f"Transport error fetching profile: {e}")
            return {"_auth_error": "offline"}
        except Exception as e:
            print(f"Error fetching profile: {e}")
            return None

    def update_profile(self, name: str, email: str) -> Optional[Dict[str, Any]]:
        """
        Update the current user's name or email.
        """
        try:
            payload = {"name": name, "email": email}
            response = requests.put(f"{self.api_url}/auth/me", json=payload, headers=self._get_headers(), timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error updating profile: {e}")
            return None

    def change_password(self, old_password: str, new_password: str) -> bool:
        """
        Change account password.
        """
        try:
            payload = {"old_password": old_password, "new_password": new_password}
            response = requests.put(f"{self.api_url}/auth/me/password", json=payload, headers=self._get_headers(), timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"Error changing password: {e}")
            return False

    def forgot_password(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Trigger password reset token generation.
        """
        try:
            payload = {"email": email}
            response = requests.post(f"{self.api_url}/auth/forgot-password", json=payload, timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error sending forgot password: {e}")
            return None

    def reset_password(self, token: str, new_password: str) -> bool:
        """
        Reset password using secure token.
        """
        try:
            payload = {"token": token, "new_password": new_password}
            response = requests.post(f"{self.api_url}/auth/reset-password", json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"Error resetting password: {e}")
            return False

    # ==========================================
    # Standard Catalog & Link & Alert Calls
    # ==========================================
    def check_health(self) -> bool:
        """
        Check if the FastAPI backend is running.
        """
        try:
            response = requests.get(self.base_url, timeout=3)
            return response.status_code == 200 and response.json().get("status") == "online"
        except Exception:
            return False

    def get_products(self) -> List[Dict[str, Any]]:
        """
        Retrieve all tracked products for the authenticated user.
        """
        try:
            response = requests.get(f"{self.api_url}/products/", headers=self._get_headers(), timeout=10)
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            print(f"Error fetching products: {e}")
            return []

    def get_product_detail(self, product_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve details of a single product including its links and alerts.
        """
        try:
            response = requests.get(f"{self.api_url}/products/{product_id}", headers=self._get_headers(), timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error fetching product detail {product_id}: {e}")
            return None

    def create_product(
        self,
        name: str,
        category: Optional[str] = None,
        initial_url: Optional[str] = None,
        initial_website: Optional[str] = None,
        target_price: Optional[float] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Orchestrate creation of a product, its initial link, and a threshold price alert.
        """
        try:
            # 1. Create product and link
            product_payload = {
                "name": name if name.strip() else "Pending Scrape",
                "category": category,
                "initial_url": initial_url,
                "initial_website": initial_website
            }
            response = requests.post(f"{self.api_url}/products/", json=product_payload, headers=self._get_headers(), timeout=15)
            if response.status_code != 201:
                return None
            
            product_data = response.json()
            product_id = product_data.get("id")

            # 2. Create alert if target price & alert contact details are provided
            if product_id and target_price is not None and (email or phone):
                alert_payload = {
                    "product_id": product_id,
                    "email": email if email else None,
                    "phone": phone if phone else None,
                    "target_price": target_price
                }
                alert_resp = requests.post(f"{self.api_url}/alerts/", json=alert_payload, headers=self._get_headers(), timeout=10)
                if alert_resp.status_code != 201:
                    print(f"Warning: Failed to create alert: {alert_resp.text}")

            return product_data
        except Exception as e:
            print(f"Error creating product: {e}")
            return None

    def delete_product(self, product_id: int) -> bool:
        """
        Delete a product group.
        """
        try:
            response = requests.delete(f"{self.api_url}/products/{product_id}", headers=self._get_headers(), timeout=10)
            return response.status_code == 204
        except Exception as e:
            print(f"Error deleting product {product_id}: {e}")
            return False

    def add_link(self, product_id: int, url: str, website: str, current_price: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Add a store tracking link to a product.
        """
        try:
            payload = {
                "product_id": product_id,
                "url": url,
                "website": website,
                "current_price": current_price
            }
            response = requests.post(f"{self.api_url}/links/", json=payload, headers=self._get_headers(), timeout=15)
            if response.status_code == 201:
                return response.json()
            return None
        except Exception as e:
            print(f"Error adding link: {e}")
            return None

    def delete_link(self, link_id: int) -> bool:
        """
        Delete a store tracking link.
        """
        try:
            response = requests.delete(f"{self.api_url}/links/{link_id}", headers=self._get_headers(), timeout=10)
            return response.status_code == 204
        except Exception as e:
            print(f"Error deleting link {link_id}: {e}")
            return False

    def check_link_now(self, link_id: int) -> Optional[Dict[str, Any]]:
        """
        Trigger an on-demand scraper run for a specific link.
        """
        try:
            response = requests.post(f"{self.api_url}/links/{link_id}/check", headers=self._get_headers(), timeout=20)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error checking link {link_id}: {e}")
            return None

    def add_alert(self, product_id: int, target_price: float, email: Optional[str] = None, phone: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Add an alert for a product.
        """
        try:
            payload = {
                "product_id": product_id,
                "email": email if email else None,
                "phone": phone if phone else None,
                "target_price": target_price
            }
            response = requests.post(f"{self.api_url}/alerts/", json=payload, headers=self._get_headers(), timeout=10)
            if response.status_code == 201:
                return response.json()
            return None
        except Exception as e:
            print(f"Error adding alert: {e}")
            return None

    def delete_alert(self, alert_id: int) -> bool:
        """
        Remove an alert from active tracking.
        """
        try:
            response = requests.delete(f"{self.api_url}/alerts/{alert_id}", headers=self._get_headers(), timeout=10)
            return response.status_code == 204
        except Exception as e:
            print(f"Error deleting alert {alert_id}: {e}")
            return False

    def get_alerts(self, product_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Fetch price alerts, optionally filtered by product_id.
        """
        try:
            params = {}
            if product_id is not None:
                params["product_id"] = product_id
            response = requests.get(f"{self.api_url}/alerts/", params=params, headers=self._get_headers(), timeout=10)
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            print(f"Error fetching alerts: {e}")
            return []

    def get_price_comparison(self, product_id: int) -> Optional[Dict[str, Any]]:
        """
        Fetch price comparison details for a product.
        """
        try:
            response = requests.get(f"{self.api_url}/products/{product_id}/comparison", headers=self._get_headers(), timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error fetching comparison for product {product_id}: {e}")
            return None

    def get_price_history(self, product_id: int) -> List[Dict[str, Any]]:
        """
        Fetch the time-series price history entries across all active links.
        """
        try:
            response = requests.get(f"{self.api_url}/analytics/{product_id}/history", headers=self._get_headers(), timeout=10)
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            print(f"Error fetching price history: {e}")
            return []

    def get_price_analytics_summary(self, product_id: int) -> Optional[Dict[str, Any]]:
        """
        Fetch summary analytics (lowest, highest, average).
        """
        try:
            response = requests.get(f"{self.api_url}/analytics/{product_id}/summary", headers=self._get_headers(), timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error fetching analytics summary: {e}")
            return None

    def get_target_price_analysis(self, product_id: int, target_price: float) -> Optional[Dict[str, Any]]:
        """
        Fetch target price analysis dates, frequency and recommendation.
        """
        try:
            response = requests.get(
                f"{self.api_url}/analytics/{product_id}/target-analysis",
                params={"target_price": target_price},
                headers=self._get_headers(),
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error fetching target analysis: {e}")
            return None

    def get_payment_optimization(self, product_id: int) -> Optional[Dict[str, Any]]:
        """
        Fetch payment method bank offer optimizations.
        """
        try:
            response = requests.get(f"{self.api_url}/products/{product_id}/payment-optimization", headers=self._get_headers(), timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error fetching payment optimization: {e}")
            return None

    def get_price_prediction(self, product_id: int, target_price: float) -> Optional[Dict[str, Any]]:
        """
        Fetch future price prediction forecasts.
        """
        try:
            response = requests.get(
                f"{self.api_url}/analytics/{product_id}/prediction",
                params={"target_price": target_price},
                headers=self._get_headers(),
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error fetching price prediction: {e}")
            return None

    def get_scheduler_status(self) -> Optional[Dict[str, Any]]:
        """
        Fetch the background scheduler status.
        """
        try:
            response = requests.get(f"{self.api_url}/scheduler/status", headers=self._get_headers(), timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error fetching scheduler status: {e}")
            return None

    def trigger_scheduler_check(self) -> bool:
        """
        Trigger an on-demand scheduled check run.
        """
        try:
            response = requests.post(f"{self.api_url}/scheduler/trigger", headers=self._get_headers(), timeout=10)
            return response.status_code == 202
        except Exception as e:
            print(f"Error triggering scheduler: {e}")
            return False

    def get_cache_statistics(self) -> Optional[Dict[str, Any]]:
        """
        Fetch cache telemetry statistics.
        """
        try:
            response = requests.get(f"{self.api_url}/scheduler/cache-stats", headers=self._get_headers(), timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error fetching cache stats: {e}")
            return None

    def get_portfolio_ai_summary(self) -> Optional[Dict[str, Any]]:
        """
        Fetch portfolio-wide AI intelligence summary stats.
        """
        try:
            response = requests.get(f"{self.api_url}/analytics/portfolio-ai-summary", headers=self._get_headers(), timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error fetching portfolio AI summary: {e}")
            return None

    def get_price_drop_analysis(self, product_id: int) -> Optional[Dict[str, Any]]:
        """
        Fetch price drop analysis for a product.
        """
        try:
            response = requests.get(f"{self.api_url}/analytics/{product_id}/price-drop", headers=self._get_headers(), timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error fetching price drop analysis: {e}")
            return None

    def get_deal_score(self, product_id: int) -> Optional[Dict[str, Any]]:
        """
        Fetch Deal Score (historical price quality) for a product.
        Separate from AI Buy Score (overall buying recommendation).
        """
        try:
            response = requests.get(f"{self.api_url}/analytics/{product_id}/deal-score", headers=self._get_headers(), timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error fetching deal score: {e}")
            return None

    def get_product_match_suggestions(self, product_id: int) -> Optional[Dict[str, Any]]:
        """
        Fetch product match suggestions (suggestion-only, no auto-merge).
        """
        try:
            response = requests.get(f"{self.api_url}/products/{product_id}/match-suggestions", headers=self._get_headers(), timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error fetching product match suggestions: {e}")
            return None
