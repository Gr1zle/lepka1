import json
import requests

API_BASE_URL = "http://127.0.0.1:8000"


class ApiClient:
    def __init__(self):
        self.token = None

    def set_token(self, token: str | None):
        self.token = token

    def _headers(self):
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(self, method: str, path: str, **kwargs):
        url = f"{API_BASE_URL}{path}"
        headers = kwargs.pop("headers", {})
        final_headers = self._headers()
        final_headers.update(headers)

        try:
            response = requests.request(method, url, headers=final_headers, timeout=20, **kwargs)
        except requests.RequestException:
            return False, "Сервер недоступен", None

        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", f"HTTP {response.status_code}")
            except Exception:
                detail = f"HTTP {response.status_code}"
            return False, detail, None

        if response.content:
            try:
                return True, "OK", response.json()
            except Exception:
                return True, "OK", None

        return True, "OK", None

    # ---------- AUTH ----------
    def register(self, email, password, nickname):
        ok, msg, data = self._request(
            "POST",
            "/auth/register",
            json={
                "email": email,
                "password": password,
                "nickname": nickname,
            },
        )
        if ok and data:
            self.set_token(data["accessToken"])
        return ok, msg, data

    def login(self, email, password):
        ok, msg, data = self._request(
            "POST",
            "/auth/login",
            json={
                "email": email,
                "password": password,
            },
        )
        if ok and data:
            self.set_token(data["accessToken"])
        return ok, msg, data

    # ---------- PROFILE ----------
    def get_me(self):
        return self._request("GET", "/profile/me")

    def update_me(self, nickname, bioText, ageCategory, favoriteColors):
        return self._request(
            "PUT",
            "/profile/me",
            json={
                "nickname": nickname,
                "bioText": bioText,
                "ageCategory": ageCategory,
                "favoriteColors": favoriteColors,
            },
        )

    def update_settings(self, themeMode, languageCode, notificationsEnabled):
        return self._request(
            "PUT",
            "/profile/settings",
            data={
                "themeMode": themeMode,
                "languageCode": languageCode,
                "notificationsEnabled": str(bool(notificationsEnabled)).lower(),
            },
        )

    # ---------- POSTS ----------
    def get_posts(self):
        return self._request("GET", "/posts")

    def create_post(self, titleText, descriptionText, categoryName, tagsText, image_file_path=None):
        data = {
            "titleText": titleText,
            "descriptionText": descriptionText,
            "categoryName": categoryName,
            "tagsText": tagsText or "",
        }

        files = None
        if image_file_path:
            files = {"image": open(image_file_path, "rb")}

        try:
            return self._request("POST", "/posts", data=data, files=files)
        finally:
            if files and files["image"]:
                files["image"].close()

    def delete_post(self, post_id):
        return self._request("DELETE", f"/posts/{post_id}")

    def toggle_like(self, post_id):
        return self._request("POST", f"/posts/{post_id}/like")

    def get_comments(self, post_id):
        return self._request("GET", f"/posts/{post_id}/comments")

    def add_comment(self, post_id, commentText):
        return self._request(
            "POST",
            f"/posts/{post_id}/comments",
            json={"commentText": commentText},
        )

    def delete_comment(self, comment_id):
        return self._request("DELETE", f"/comments/{comment_id}")

    # ---------- PROJECTS ----------
    def get_projects(self):
        return self._request("GET", "/projects")

    def create_project(self, projectName, categoryName, deadlineDate, descriptionText):
        return self._request(
            "POST",
            "/projects",
            json={
                "projectName": projectName,
                "categoryName": categoryName,
                "deadlineDate": deadlineDate or "",
                "descriptionText": descriptionText or "",
            },
        )

    def delete_project(self, project_id):
        return self._request("DELETE", f"/projects/{project_id}")

    def add_project_step(self, project_id, stepDescription):
        return self._request(
            "POST",
            f"/projects/{project_id}/steps",
            json={"stepDescription": stepDescription},
        )

    def patch_step(self, step_id, isCompleted):
        return self._request(
            "PATCH",
            f"/project-steps/{step_id}",
            json={"isCompleted": bool(isCompleted)},
        )

    def delete_step(self, step_id):
        return self._request("DELETE", f"/project-steps/{step_id}")

    # ---------- MIXTURES ----------
    def get_mixtures(self):
        return self._request("GET", "/mixtures")

    def create_mixture(self, mixtureName, resultHex, totalWeight, recipeItems):
        return self._request(
            "POST",
            "/mixtures",
            json={
                "mixtureName": mixtureName,
                "resultHex": resultHex,
                "totalWeight": totalWeight,
                "recipeItems": recipeItems,
            },
        )


api_client = ApiClient()