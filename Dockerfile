FROM python:3.13-slim
LABEL maintainer="@AnnikenYT"

WORKDIR /app
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
RUN pip uninstall -y py-cord discord
RUN pip install --no-cache-dir py-cord
COPY . .
CMD ["python", "main.py"]