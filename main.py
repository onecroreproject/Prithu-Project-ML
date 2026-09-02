# ============================================================
# PRITHU RFRE BACKEND - MAIN API
# ============================================================

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from fastapi.middleware.cors import CORSMiddleware

from database import (
    init_database,
    close_database,
    database_health,
    insert_content
)

from models import (
    RecommendRequest,
    SeenRequest,
    ContentCreateRequest
)

from engine import (
    generate_feed,
    mark_viewed
)

from scheduler import (
    refresh_daily_feed
)


# ============================================================
# APPLICATION LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    # --------------------------------------------------------
    # STARTUP
    # --------------------------------------------------------

    try:

        init_database()

        print(
            "===================================="
        )

        print(
            "Prithu RFRE Backend Started"
        )

        print(
            "MongoDB Atlas Database Initialized"
        )

        print(
            "===================================="
        )

    except Exception as e:

        print(
            "===================================="
        )

        print(
            "MONGODB INITIALIZATION FAILED"
        )

        print(
            "===================================="
        )

        print(
            f"Error: {e}"
        )

        raise

    yield

    # --------------------------------------------------------
    # SHUTDOWN
    # --------------------------------------------------------

    close_database()

    print(
        "===================================="
    )

    print(
        "Prithu RFRE Backend Stopped"
    )

    print(
        "===================================="
    )


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(

    title=
        "Prithu RFRE API",

    version=
        "1.0.0",

    description=
        (
            "Rule-Based Feed Recommendation "
            "Engine for Prithu using "
            "MongoDB Atlas"
        ),

    lifespan=
        lifespan
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(

    CORSMiddleware,

    allow_origins=[
        "*"
    ],

    allow_credentials=
        True,

    allow_methods=[
        "*"
    ],

    allow_headers=[
        "*"
    ]
)


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {

        "success":
            True,

        "application":
            "Prithu",

        "engine":
            "RFRE",

        "database":
            "MongoDB Atlas",

        "status":
            "online"
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():

    mongo_status = (
        database_health()
    )

    return {

        "success":
            mongo_status,

        "status":
            (
                "healthy"
                if mongo_status
                else "unhealthy"
            ),

        "engine":
            "RFRE",

        "database":
            "MongoDB Atlas",

        "mongodb":
            (
                "connected"
                if mongo_status
                else "disconnected"
            )
    }


# ============================================================
# RECOMMEND
# ============================================================

@app.post("/recommend")
def recommend(
    request: RecommendRequest
):

    try:

        result = generate_feed(

            user_id=
                request.userId,

            limit=
                request.limit,

            prefer_short=
                request.preferShort,

            exclude_ids=
                request.excludeIds
        )

        return result

    except Exception as e:

        raise HTTPException(

            status_code=500,

            detail={

                "success":
                    False,

                "message":
                    "Recommendation generation failed",

                "error":
                    str(e)
            }
        )


# ============================================================
# MARK CONTENT AS SEEN
# ============================================================

@app.post("/seen")
def seen(
    request: SeenRequest
):

    try:

        result = mark_viewed(

            user_id=
                request.userId,

            content_id=
                request.contentId
        )

        return result

    except Exception as e:

        raise HTTPException(

            status_code=500,

            detail={

                "success":
                    False,

                "message":
                    "Unable to mark content as viewed",

                "error":
                    str(e)
            }
        )


# ============================================================
# CREATE CONTENT
# ============================================================

@app.post("/content")
def create_content(
    request: ContentCreateRequest
):

    try:

        content_id = insert_content({

            "title":
                request.title,

            "category":
                request.category,

            "tags":
                request.tags,

            "post_type":
                request.post_type,

            "media_url":
                request.media_url,

            "publish_date":
                request.publish_date,

            "expiry_date":
                request.expiry_date,

            "weekday":
                request.weekday,

            "time_slot":
                request.time_slot,

            "festival":
                request.festival,

            "priority":
                request.priority,

            "duration":
                request.duration
        })

        return {

            "success":
                True,

            "message":
                "Content created successfully",

            "content_id":
                content_id
        }

    except Exception as e:

        raise HTTPException(

            status_code=500,

            detail={

                "success":
                    False,

                "message":
                    "Content creation failed",

                "error":
                    str(e)
            }
        )


# ============================================================
# DAILY REFRESH
# ============================================================

@app.post("/refresh")
def refresh():

    try:

        result = (
            refresh_daily_feed()
        )

        return result

    except Exception as e:

        raise HTTPException(

            status_code=500,

            detail={

                "success":
                    False,

                "message":
                    "Daily content refresh failed",

                "error":
                    str(e)
            }
        )


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(

        app,

        host=
            "0.0.0.0",

        port=
            8001
    )

