from fastapi.templating import Jinja2Templates
import os

# Caminho absoluto para os templates (relativo ao arquivo atual)
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(_BASE, "templates"))
