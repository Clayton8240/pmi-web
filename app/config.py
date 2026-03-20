import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://mentor:MM%26Br4zil@localhost/pmi_etiquetas")
OUTPUT_FOLDER: str = os.getenv("OUTPUT_FOLDER", "etiquetas_geradas")
EMPRESA_NOME: str = os.getenv("EMPRESA_NOME", "Mentor Brasil")
TRANSPORTADORA_PADRAO: str = os.getenv("TRANSPORTADORA_PADRAO", "New Pratika Express Ltda")
