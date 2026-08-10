FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

COPY --chmod=755 entrypoint.sh . 

ENTRYPOINT ["./entrypoint.sh"]

CMD ["python", "-m", "experiments.sqlalchemy_1_4_vs_2_0.app"]