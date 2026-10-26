import json
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import init_db, get_conn
from auth import hash_password, verify_password, create_access_token, parse_token
from schemas import (
    RegisterBody,
    LoginBody,
    TokenResponse,
    ProfileResponse,
    UpdateProfileBody,
    PostCommentBody,
    ProjectBody,
    ProjectStepBody,
    StepPatchBody,
    MixtureBody,
)

UPLOADS_DIR = Path("uploads")
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Lepka Helper API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # локальная защита: для демо так можно
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


def _row_to_dict(row):
    return dict(row) if row is not None else None


def get_current_user(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    token = authorization.replace("Bearer ", "")
    payload = parse_token(token)

    if not payload:
        raise HTTPException(status_code=401, detail="Недействительный токен")

    user_id = int(payload["sub"])

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE userId = ?", (user_id,))
    user = cur.fetchone()
    conn.close()

    if user is None:
        raise HTTPException(status_code=401, detail="Пользователь не найден")

    return user


@app.on_event("startup")
def startup():
    init_db()


# ------------------ AUTH ------------------ #

@app.post("/auth/register", response_model=TokenResponse)
def register(body: RegisterBody):
    email = body.email.strip().lower()
    nickname = body.nickname.strip()
    password = body.password

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT userId FROM users WHERE email = ?", (email,))
    if cur.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Пользователь с таким email уже зарегистрирован")

    cur.execute("SELECT userId FROM users WHERE nickname = ?", (nickname,))
    if cur.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Такой никнейм уже занят")

    password_hash = hash_password(password)

    cur.execute(
        """
        INSERT INTO users (email, passwordHash, nickname)
        VALUES (?, ?, ?)
        """,
        (email, password_hash, nickname),
    )
    user_id = cur.lastrowid
    conn.commit()
    conn.close()

    token = create_access_token(user_id, email)

    return TokenResponse(
        accessToken=token,
        tokenType="bearer",
        userId=user_id,
        email=email,
        nickname=nickname,
        roleName="user",
    )


@app.post("/auth/login", response_model=TokenResponse)
def login(body: LoginBody):
    email = body.email.strip().lower()

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cur.fetchone()
    conn.close()

    if not user:
        raise HTTPException(status_code=400, detail="Неверный email или пароль")

    if user["isBlocked"] == 1:
        raise HTTPException(status_code=403, detail="Аккаунт заблокирован")

    if not verify_password(body.password, user["passwordHash"]):
        raise HTTPException(status_code=400, detail="Неверный email или пароль")

    token = create_access_token(user["userId"], user["email"])

    return TokenResponse(
        accessToken=token,
        tokenType="bearer",
        userId=user["userId"],
        email=user["email"],
        nickname=user["nickname"],
        roleName=user["roleName"],
    )


# ------------------ PROFILE ------------------ #

@app.get("/profile/me", response_model=ProfileResponse)
def get_profile_me(user=Depends(get_current_user)):
    try:
        favorite_colors = json.loads(user["favoriteColorsJson"] or "[]")
    except Exception:
        favorite_colors = []

    return ProfileResponse(
        userId=user["userId"],
        email=user["email"],
        nickname=user["nickname"],
        roleName=user["roleName"],
        bioText=user["bioText"] or "",
        ageCategory=user["ageCategory"] or "Взрослый 18+",
        favoriteColors=favorite_colors,
        themeMode=user["themeMode"] or "light",
        languageCode=user["languageCode"] or "ru",
        notificationsEnabled=bool(user["notificationsEnabled"]),
    )


@app.put("/profile/me", response_model=ProfileResponse)
def update_profile_me(body: UpdateProfileBody, user=Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()

    new_nickname = body.nickname.strip()
    cur.execute("SELECT userId FROM users WHERE nickname = ?", (new_nickname,))
    existing = cur.fetchone()
    if existing and existing["userId"] != user["userId"]:
        conn.close()
        raise HTTPException(status_code=400, detail="Такой никнейм уже занят")

    cur.execute(
        """
        UPDATE users
        SET nickname = ?, bioText = ?, ageCategory = ?, favoriteColorsJson = ?
        WHERE userId = ?
        """,
        (
            new_nickname,
            body.bioText.strip(),
            body.ageCategory,
            json.dumps(body.favoriteColors, ensure_ascii=False),
            user["userId"],
        ),
    )
    conn.commit()
    conn.close()

    # читаем заново
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE userId = ?", (user["userId"],))
    updated = cur.fetchone()
    conn.close()

    try:
        favorite_colors = json.loads(updated["favoriteColorsJson"] or "[]")
    except Exception:
        favorite_colors = []

    return ProfileResponse(
        userId=updated["userId"],
        email=updated["email"],
        nickname=updated["nickname"],
        roleName=updated["roleName"],
        bioText=updated["bioText"] or "",
        ageCategory=updated["ageCategory"] or "Взрослый 18+",
        favoriteColors=favorite_colors,
        themeMode=updated["themeMode"] or "light",
        languageCode=updated["languageCode"] or "ru",
        notificationsEnabled=bool(updated["notificationsEnabled"]),
    )


@app.put("/profile/settings")
def update_profile_settings(
    themeMode: str = Form(...),
    languageCode: str = Form(...),
    notificationsEnabled: bool = Form(...),
    user=Depends(get_current_user),
):
    if themeMode not in ["light", "dark"]:
        raise HTTPException(status_code=400, detail="Некорректная тема")
    if languageCode not in ["ru", "en"]:
        raise HTTPException(status_code=400, detail="Некорректный язык")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE users
        SET themeMode = ?, languageCode = ?, notificationsEnabled = ?
        WHERE userId = ?
        """,
        (themeMode, languageCode, 1 if notificationsEnabled else 0, user["userId"]),
    )
    conn.commit()
    conn.close()

    return {"message": "Настройки сохранены"}


# ------------------ POSTS ------------------ #

@app.get("/posts")
def get_posts():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            posts.postId,
            posts.userId,
            posts.titleText,
            posts.descriptionText,
            posts.categoryName,
            posts.tagsText,
            posts.imagePath,
            posts.likesCount,
            posts.createdAt,
            users.nickname
        FROM posts
        INNER JOIN users ON users.userId = posts.userId
        ORDER BY posts.createdAt DESC
        """
    )
    rows = cur.fetchall()
    conn.close()

    return [_row_to_dict(row) for row in rows]


@app.post("/posts")
async def create_post(
    titleText: str = Form(...),
    descriptionText: str = Form(...),
    categoryName: str = Form(...),
    tagsText: str = Form(default=""),
    image: Optional[UploadFile] = File(default=None),
    user=Depends(get_current_user),
):
    clean_title = titleText.strip()
    clean_desc = descriptionText.strip()
    clean_tags = tagsText.strip()

    if len(clean_title) < 3 or len(clean_title) > 100:
        raise HTTPException(status_code=400, detail="Название работы должно быть 3-100 символов")
    if len(clean_desc) < 10 or len(clean_desc) > 2000:
        raise HTTPException(status_code=400, detail="Описание должно быть 10-2000 символов")

    image_path = ""
    if image and image.filename:
        ext = Path(image.filename).suffix.lower()
        if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
            raise HTTPException(status_code=400, detail="Разрешены только jpg/jpeg/png/webp")

        file_name = f"{uuid.uuid4().hex}{ext}"
        save_path = UPLOADS_DIR / file_name

        contents = await image.read()
        if len(contents) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Файл слишком большой (макс 10 МБ)")

        save_path.write_bytes(contents)
        image_path = f"/uploads/{file_name}"

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO posts (
            userId, titleText, descriptionText, categoryName, tagsText, imagePath
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user["userId"],
            clean_title,
            clean_desc,
            categoryName,
            clean_tags,
            image_path,
        ),
    )
    post_id = cur.lastrowid
    conn.commit()
    conn.close()

    return {"message": "Работа опубликована", "postId": post_id}


@app.delete("/posts/{post_id}")
def delete_post(post_id: int, user=Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM posts WHERE postId = ?", (post_id,))
    post = cur.fetchone()
    if not post:
        conn.close()
        raise HTTPException(status_code=404, detail="Пост не найден")

    if post["userId"] != user["userId"]:
        conn.close()
        raise HTTPException(status_code=403, detail="Нет прав на удаление")

    # удаляем файл изображения
    if post["imagePath"]:
        filename = post["imagePath"].replace("/uploads/", "")
        file_path = UPLOADS_DIR / filename
        if file_path.exists():
            file_path.unlink(missing_ok=True)

    cur.execute("DELETE FROM posts WHERE postId = ?", (post_id,))
    conn.commit()
    conn.close()

    return {"message": "Публикация удалена"}


@app.post("/posts/{post_id}/like")
def toggle_like(post_id: int, user=Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT postId FROM posts WHERE postId = ?", (post_id,))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Пост не найден")

    cur.execute(
        "SELECT likeId FROM postLikes WHERE postId = ? AND userId = ?",
        (post_id, user["userId"]),
    )
    existing_like = cur.fetchone()

    if existing_like:
        cur.execute(
            "DELETE FROM postLikes WHERE postId = ? AND userId = ?",
            (post_id, user["userId"]),
        )
        is_liked = False
    else:
        cur.execute(
            "INSERT INTO postLikes (postId, userId) VALUES (?, ?)",
            (post_id, user["userId"]),
        )
        is_liked = True

    cur.execute("SELECT COUNT(*) as cnt FROM postLikes WHERE postId = ?", (post_id,))
    likes_count = cur.fetchone()["cnt"]

    cur.execute("UPDATE posts SET likesCount = ? WHERE postId = ?", (likes_count, post_id))

    conn.commit()
    conn.close()

    return {"isLiked": is_liked, "likesCount": likes_count}


@app.get("/posts/{post_id}/comments")
def get_post_comments(post_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            postComments.commentId,
            postComments.postId,
            postComments.userId,
            postComments.commentText,
            postComments.createdAt,
            users.nickname
        FROM postComments
        INNER JOIN users ON users.userId = postComments.userId
        WHERE postComments.postId = ?
        ORDER BY postComments.createdAt ASC
        """,
        (post_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return [_row_to_dict(row) for row in rows]


@app.post("/posts/{post_id}/comments")
def add_post_comment(post_id: int, body: PostCommentBody, user=Depends(get_current_user)):
    text = body.commentText.strip()
    if len(text) < 5 or len(text) > 1000:
        raise HTTPException(status_code=400, detail="Комментарий должен быть 5-1000 символов")

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT postId FROM posts WHERE postId = ?", (post_id,))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Пост не найден")

    cur.execute(
        """
        INSERT INTO postComments (postId, userId, commentText)
        VALUES (?, ?, ?)
        """,
        (post_id, user["userId"], text),
    )
    comment_id = cur.lastrowid
    conn.commit()
    conn.close()

    return {"message": "Комментарий добавлен", "commentId": comment_id}


@app.delete("/comments/{comment_id}")
def delete_comment(comment_id: int, user=Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM postComments WHERE commentId = ?", (comment_id,))
    comment = cur.fetchone()
    if not comment:
        conn.close()
        raise HTTPException(status_code=404, detail="Комментарий не найден")

    if comment["userId"] != user["userId"]:
        conn.close()
        raise HTTPException(status_code=403, detail="Нет прав на удаление комментария")

    cur.execute("DELETE FROM postComments WHERE commentId = ?", (comment_id,))
    conn.commit()
    conn.close()

    return {"message": "Комментарий удалён"}


# ------------------ PROJECTS ------------------ #

def recalc_project_progress(project_id: int):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT stepId, isCompleted FROM projectSteps WHERE projectId = ?", (project_id,))
    steps = cur.fetchall()

    if not steps:
        progress = 0.0
    else:
        done = sum(1 for s in steps if s["isCompleted"] == 1)
        progress = round(done / len(steps) * 100, 1)

    cur.execute("UPDATE projects SET progressPercent = ? WHERE projectId = ?", (progress, project_id))
    conn.commit()
    conn.close()
    return progress


@app.get("/projects")
def get_projects(user=Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM projects
        WHERE userId = ?
        ORDER BY createdAt DESC
        """,
        (user["userId"],),
    )
    projects = cur.fetchall()

    result = []
    for p in projects:
        project_id = p["projectId"]
        cur.execute(
            """
            SELECT stepId, projectId, stepDescription, isCompleted, createdAt
            FROM projectSteps
            WHERE projectId = ?
            ORDER BY createdAt ASC
            """,
            (project_id,),
        )
        steps = cur.fetchall()

        result.append({
            "projectId": p["projectId"],
            "userId": p["userId"],
            "projectName": p["projectName"],
            "categoryName": p["categoryName"],
            "deadlineDate": p["deadlineDate"] or "",
            "descriptionText": p["descriptionText"] or "",
            "progressPercent": p["progressPercent"],
            "createdAt": p["createdAt"],
            "stepItems": [_row_to_dict(s) for s in steps],
        })

    conn.close()
    return result


@app.post("/projects")
def create_project(body: ProjectBody, user=Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO projects (userId, projectName, categoryName, deadlineDate, descriptionText)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            user["userId"],
            body.projectName.strip(),
            body.categoryName,
            body.deadlineDate or "",
            (body.descriptionText or "").strip(),
        ),
    )
    project_id = cur.lastrowid
    conn.commit()
    conn.close()

    return {"message": "Проект сохранён", "projectId": project_id}


@app.delete("/projects/{project_id}")
def delete_project(project_id: int, user=Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM projects WHERE projectId = ?", (project_id,))
    project = cur.fetchone()
    if not project:
        conn.close()
        raise HTTPException(status_code=404, detail="Проект не найден")

    if project["userId"] != user["userId"]:
        conn.close()
        raise HTTPException(status_code=403, detail="Нет прав на удаление проекта")

    cur.execute("DELETE FROM projects WHERE projectId = ?", (project_id,))
    conn.commit()
    conn.close()

    return {"message": "Проект удалён"}


@app.post("/projects/{project_id}/steps")
def add_project_step(project_id: int, body: ProjectStepBody, user=Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM projects WHERE projectId = ?", (project_id,))
    project = cur.fetchone()
    if not project:
        conn.close()
        raise HTTPException(status_code=404, detail="Проект не найден")

    if project["userId"] != user["userId"]:
        conn.close()
        raise HTTPException(status_code=403, detail="Нет прав на изменение проекта")

    cur.execute(
        """
        INSERT INTO projectSteps (projectId, stepDescription, isCompleted)
        VALUES (?, ?, 0)
        """,
        (project_id, body.stepDescription.strip()),
    )
    step_id = cur.lastrowid
    conn.commit()
    conn.close()

    progress = recalc_project_progress(project_id)
    return {"message": "Этап добавлен", "stepId": step_id, "progressPercent": progress}


@app.patch("/project-steps/{step_id}")
def patch_project_step(step_id: int, body: StepPatchBody, user=Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT projectSteps.*, projects.userId as ownerId
        FROM projectSteps
        INNER JOIN projects ON projects.projectId = projectSteps.projectId
        WHERE projectSteps.stepId = ?
        """,
        (step_id,),
    )
    step = cur.fetchone()
    if not step:
        conn.close()
        raise HTTPException(status_code=404, detail="Этап не найден")

    if step["ownerId"] != user["userId"]:
        conn.close()
        raise HTTPException(status_code=403, detail="Нет прав на изменение этапа")

    cur.execute(
        "UPDATE projectSteps SET isCompleted = ? WHERE stepId = ?",
        (1 if body.isCompleted else 0, step_id),
    )
    conn.commit()
    conn.close()

    progress = recalc_project_progress(step["projectId"])
    return {"message": "Статус этапа обновлён", "progressPercent": progress}


@app.delete("/project-steps/{step_id}")
def delete_project_step(step_id: int, user=Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT projectSteps.*, projects.userId as ownerId
        FROM projectSteps
        INNER JOIN projects ON projects.projectId = projectSteps.projectId
        WHERE projectSteps.stepId = ?
        """,
        (step_id,),
    )
    step = cur.fetchone()

    if not step:
        conn.close()
        raise HTTPException(status_code=404, detail="Этап не найден")

    if step["ownerId"] != user["userId"]:
        conn.close()
        raise HTTPException(status_code=403, detail="Нет прав на удаление этапа")

    project_id = step["projectId"]
    cur.execute("DELETE FROM projectSteps WHERE stepId = ?", (step_id,))
    conn.commit()
    conn.close()

    progress = recalc_project_progress(project_id)
    return {"message": "Этап удалён", "progressPercent": progress}


# ------------------ MIXTURES ------------------ #

@app.get("/mixtures")
def get_mixtures(user=Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT mixtureId, userId, mixtureName, resultHex, totalWeight, recipeJson, createdAt
        FROM colorMixtures
        WHERE userId = ?
        ORDER BY createdAt DESC
        """,
        (user["userId"],),
    )
    rows = cur.fetchall()
    conn.close()

    result = []
    for row in rows:
        row_dict = _row_to_dict(row)
        try:
            row_dict["recipeItems"] = json.loads(row_dict["recipeJson"])
        except Exception:
            row_dict["recipeItems"] = []
        result.append(row_dict)

    return result


@app.post("/mixtures")
def create_mixture(body: MixtureBody, user=Depends(get_current_user)):
    if body.totalWeight <= 0:
        raise HTTPException(status_code=400, detail="Общий вес должен быть больше 0")

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO colorMixtures (userId, mixtureName, resultHex, totalWeight, recipeJson)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            user["userId"],
            body.mixtureName.strip(),
            body.resultHex.strip().upper(),
            body.totalWeight,
            json.dumps(body.recipeItems, ensure_ascii=False),
        ),
    )
    mixture_id = cur.lastrowid
    conn.commit()
    conn.close()

    return {"message": "Смесь сохранена", "mixtureId": mixture_id}