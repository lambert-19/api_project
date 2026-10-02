"""Page /docs personnalisée : Swagger UI avec les codes de réponse colorés.

📖 Doc FastAPI : How To → Custom Docs UI Static Assets
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse, HTMLResponse

STYLE = Path(__file__).parent / "static" / "swagger.css"

# Les réponses obtenues avec « Try it out » n'ont pas d'attribut data-code :
# on le recopie depuis le texte de la cellule, pour que les couleurs s'appliquent aussi
SCRIPT_CODES_REPONSES = """
<script>
new MutationObserver(() => {
  document.querySelectorAll(".live-responses-table tr.response:not([data-code])").forEach((ligne) => {
    const code = ligne.querySelector(".response-col_status")?.firstChild?.textContent.trim();
    if (code) ligne.dataset.code = code;
  });
}).observe(document.body, { childList: true, subtree: true });
</script>
"""


def installer_documentation(app: FastAPI) -> None:
    """Remplace la page /docs par défaut (créer l'app avec docs_url=None)."""

    @app.get("/docs", include_in_schema=False)
    def swagger() -> HTMLResponse:
        page = get_swagger_ui_html(
            openapi_url=app.openapi_url or "/openapi.json",
            title=f"{app.title} - Documentation",
            swagger_css_url="/docs/style.css",
            swagger_ui_parameters=app.swagger_ui_parameters,
        )
        html = bytes(page.body).decode().replace("</body>", f"{SCRIPT_CODES_REPONSES}</body>")
        return HTMLResponse(html)

    @app.get("/docs/style.css", include_in_schema=False)
    def style() -> FileResponse:
        return FileResponse(STYLE, media_type="text/css")
