import os
import json
import logging
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BRASIL_OFFSET = timedelta(hours=-3)

def get_data_brasil():
    agora_utc = datetime.now(timezone.utc)
    agora_brasil = agora_utc.astimezone(timezone(BRASIL_OFFSET))
    return agora_brasil.strftime("%d/%m/%Y %H:%M")

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# === SUPABASE ===
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
supabase_client = None

def init_supabase():
    global supabase_client
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning("⚠️ Supabase não configurado (SUPABASE_URL / SUPABASE_KEY ausentes)")
        return
    try:
        from supabase import create_client
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("✅ Supabase conectado")
    except Exception as e:
        logger.error(f"❌ Erro ao conectar ao Supabase: {e}")

def salvar_relatorio(dados: dict):
    if not supabase_client:
        return
    try:
        supabase_client.table("relatorios").insert(dados).execute()
        logger.info(f"✅ Relatório salvo - {dados.get('tecnico')}")
    except Exception as e:
        logger.error(f"❌ Erro ao salvar no Supabase: {e}")

# === MATERIAIS ===
def carregar_materiais():
    materiais = []
    try:
        caminho = os.path.join(os.path.dirname(__file__), "materiais.txt")
        if not os.path.exists(caminho):
            return [{"nome": "CONECTOR APC", "categoria": "Conectores"}]
        with open(caminho, "r", encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if not linha or linha.startswith('#'):
                    continue
                partes = linha.split('|')
                if len(partes) >= 2:
                    materiais.append({"nome": partes[0].strip(), "categoria": partes[1].strip()})
        logger.info(f"✅ {len(materiais)} materiais carregados")
        return materiais
    except Exception as e:
        logger.error(f"❌ Erro ao carregar materiais: {e}")
        return [{"nome": "CONECTOR APC", "categoria": "Conectores"}]

MATERIAIS_CACHE = None

@app.on_event("startup")
async def startup_event():
    global MATERIAIS_CACHE
    MATERIAIS_CACHE = carregar_materiais()
    init_supabase()
    logger.info(f"🚀 Servidor iniciado - {len(MATERIAIS_CACHE)} materiais")

@app.get("/.well-known/appspecific/com.chrome.devtools.json", include_in_schema=False)
async def devtools_config():
    return JSONResponse(content={})

@app.get("/", response_class=HTMLResponse)
async def index():
    try:
        caminho = os.path.join(os.path.dirname(__file__), "index.html")
        with open(caminho, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except Exception as e:
        return HTMLResponse(content=f"<h1>Erro: {e}</h1>", status_code=500)

@app.get("/api/materiais")
async def get_materiais():
    return JSONResponse(content={"materiais": MATERIAIS_CACHE, "total": len(MATERIAIS_CACHE)})

@app.post("/api/materiais/recarregar")
async def recarregar_materiais():
    global MATERIAIS_CACHE
    MATERIAIS_CACHE = carregar_materiais()
    return JSONResponse(content={"mensagem": f"{len(MATERIAIS_CACHE)} materiais recarregados", "total": len(MATERIAIS_CACHE)})

@app.get("/api/debug/materiais")
async def debug_materiais():
    caminho = os.path.join(os.path.dirname(__file__), "materiais.txt")
    existe = os.path.exists(caminho)
    conteudo = ""
    if existe:
        with open(caminho, "r", encoding="utf-8") as f:
            conteudo = f.read()
    return JSONResponse(content={
        "caminho": caminho,
        "existe": existe,
        "conteudo": conteudo[:500] + "..." if len(conteudo) > 500 else conteudo,
        "materiais_no_cache": len(MATERIAIS_CACHE) if MATERIAIS_CACHE else 0
    })

@app.post("/gerar_relatorio")
async def gerar_relatorio(request: Request):
    try:
        body = await request.body()
        data = json.loads(body)

        tecnico              = data.get("tecnico", "").strip()
        relatorio_texto      = data.get("relatorio_texto", "").strip()
        problema_tecnico     = data.get("problema_tecnico", "").strip()
        equipamento_status   = data.get("equipamento_status", "").strip()
        equipamento_obs      = data.get("equipamento_obs", "").strip()
        maior_sinal          = data.get("maior_sinal", "").strip()
        materiais_utilizados = data.get("materiais_utilizados", "").strip()
        materiais_recolhidos = data.get("materiais_recolhidos", "").strip()
        checklist_fotos      = data.get("checklist_fotos", "").strip()
        obs_fotos            = data.get("obs_fotos", "").strip()

        data_atual = get_data_brasil()

        relatorio = f"""
-------------------------------------
Relatório Técnico - {data_atual}
-------------------------------------

> Técnico: {tecnico}

Situação encontrado:
{relatorio_texto}

Resolução do Problema:
{problema_tecnico}

Cabeou o(s) Equipamento(s): {equipamento_status}
OBS: {equipamento_obs}

Maior sinal de RSSI: {maior_sinal}

Materiais Utilizados:
{materiais_utilizados if materiais_utilizados else "Nenhum"}

Materiais Recolhidos:
{materiais_recolhidos if materiais_recolhidos else "Nenhum"}
{f'''
{checklist_fotos}''' if checklist_fotos else ''}
-------------------------------------
""".strip()

        # Salva no Supabase em background — falha silenciosa para não travar o técnico
        salvar_relatorio({
            "tecnico":              tecnico,
            "situacao_encontrada":  relatorio_texto,
            "resolucao_problema":   problema_tecnico,
            "equipamento_status":   equipamento_status,
            "equipamento_obs":      equipamento_obs,
            "maior_sinal":          maior_sinal,
            "materiais_utilizados": materiais_utilizados,
            "materiais_recolhidos": materiais_recolhidos,
            "obs_fotos":            obs_fotos,
            "check_sinal_fibra":    data.get("check_sinal_fibra") == "sim",
            "check_serial":         data.get("check_serial") == "sim",
            "check_cto":            data.get("check_cto") == "sim",
            "check_panoramica":     data.get("check_panoramica") == "sim",
            "check_sobra":          data.get("check_sobra") == "sim",
            "check_metragem":       data.get("check_metragem") == "sim",
            "check_velocidade":     data.get("check_velocidade") == "sim",
            "check_local_ont":      data.get("check_local_ont") == "sim",
            "check_frente":         data.get("check_frente") == "sim",
            "relatorio_completo":   relatorio,
        })

        logger.info(f"✅ Relatório gerado - {tecnico}")
        return JSONResponse(content={"relatorio": relatorio})

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Formato inválido: {str(e)}")
    except Exception as e:
        logger.error(f"❌ Erro interno: {e}")
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")

@app.get("/api/relatorios")
async def listar_relatorios(limite: int = 50, tecnico: str = None):
    if not supabase_client:
        raise HTTPException(status_code=503, detail="Banco de dados não configurado")
    try:
        query = supabase_client.table("relatorios").select(
            "id, criado_em, tecnico, equipamento_status, maior_sinal, "
            "check_sinal_fibra, check_serial, check_cto, check_panoramica, "
            "check_sobra, check_metragem, check_velocidade, check_local_ont, check_frente"
        ).order("criado_em", desc=True).limit(limite)
        if tecnico:
            query = query.eq("tecnico", tecnico)
        result = query.execute()
        return JSONResponse(content={"relatorios": result.data, "total": len(result.data)})
    except Exception as e:
        logger.error(f"❌ Erro ao listar relatórios: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/relatorios/{relatorio_id}")
async def get_relatorio(relatorio_id: str):
    if not supabase_client:
        raise HTTPException(status_code=503, detail="Banco de dados não configurado")
    try:
        result = supabase_client.table("relatorios").select("*").eq("id", relatorio_id).single().execute()
        return JSONResponse(content=result.data)
    except Exception as e:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "timezone": "America/Sao_Paulo (UTC-3)",
        "data_brasil": get_data_brasil(),
        "data_utc": datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M"),
        "materiais_carregados": len(MATERIAIS_CACHE) if MATERIAIS_CACHE else 0,
        "supabase": "conectado" if supabase_client else "não configurado",
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
