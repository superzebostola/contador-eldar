# Usar Python 3.11 (evita erro do audioop)
FROM python:3.11-slim

# Diretório de trabalho dentro do container
WORKDIR /app

# Copiar arquivos do projeto
COPY . .

# Instalar dependências
RUN pip install --no-cache-dir -r requirements.txt

# Rodar o bot
CMD ["python", "main.py"]
