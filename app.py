from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from scrapers.router import importer

app = FastAPI(title="Israel Market Importer")

templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )


@app.post("/importer", response_class=HTMLResponse)
async def importer_page(request: Request, url: str = Form(...)):

    try:
        produits = importer(url)

        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "url": url,
                "produits": produits,
                "message": f"✅ {len(produits)} produits trouvés"
            }
        )

    except Exception as e:

        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "url": url,
                "message": f"❌ Erreur : {str(e)}"
            }
        )