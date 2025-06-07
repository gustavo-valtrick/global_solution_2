import pandas as pd

# 1) Ler o CSV bruto (separado por ponto-e-vírgula)
df = pd.read_csv("dataset_gs.csv", sep=";")

# 2) Converter data e ordenar
df["Data"] = pd.to_datetime(df["Data Medicao"])
df = df.sort_values("Data")

# 3) Renomear/selecionar a coluna de precipitação diária
COL_CHUVA = "PRECIPITACAO TOTAL, DIARIO (AUT)(mm)"    # ajuste se o nome for outro
df["chuva_dia"] = df[COL_CHUVA]

# 4) Calcular acumulados de 3 e 5 dias
df["chuva_3d"] = df["chuva_dia"].rolling(3).sum()
df["chuva_5d"] = df["chuva_dia"].rolling(5).sum()

# 5) Gerar etiqueta de risco (regra simples; pode refinar depois)
df["classe"] = ((df["chuva_3d"] > 120) | (df["chuva_5d"] > 180)).astype(int)

# 6) Selecionar apenas o que interessa
cols_out = ["Data", "chuva_dia", "chuva_3d", "chuva_5d", "classe"]
df_out = df[cols_out].dropna()          # descarta linhas sem acumulado (primeiros dias)

# 7) Salvar CSV pronto para treino
df_out.to_csv("dados_flood_rot.csv", index=False)
print("Arquivo salvo: dados_flood_rot.csv  –  linhas:", len(df_out))
