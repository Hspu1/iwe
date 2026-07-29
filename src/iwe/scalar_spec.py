from typing import Final

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

THEME: Final[str] = "Saturn"
LAYOUT: Final[str] = "classic"


def mount_standalone(app: FastAPI) -> None:
    app.mount("/assets", StaticFiles(directory="/opt/scalar"), name="assets")

    @app.get("/docs", include_in_schema=False)
    async def scalar_docs() -> HTMLResponse:
        html_content = f"""
        <!doctype html>
        <html>
          <head>
            <title>{app.title} - API Reference</title>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <style>
              body {{ margin: 0; }}
            </style>
          </head>
          <body>
            <script
              id="api-reference"
              data-url="/openapi.json"
              data-configuration='{{
                "theme": "{THEME}",
                "layout": "{LAYOUT}",
                "hideDownloadButton": true,
                "hideClientButton": true,
                "hiddenClients": true,
                "hideSearch": true
              }}'>
            </script>
            <script src="/assets/scalar.js"></script> 
          </body>
        </html>
        """
        return HTMLResponse(content=html_content)
