# treina_modelo.py
# -----------------------------------------------------------
# Treina um RandomForest para classificar dias de "risco" (1)
# ou "normal" (0) usando o dataset já pré-processado.

import pandas as pd, joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report

# 1) Carregar o CSV que você gerou no passo anterior
df = pd.read_csv("dados_flood_rot.csv")

# 2) Features (X) e alvo (y)
X = df[["chuva_dia", "chuva_3d", "chuva_5d"]]
y = df["classe"]

# 3) Separa treino e teste (75 % / 25 %)
Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25,
                                      random_state=42, stratify=y)

# 4) Treina RandomForest
clf = RandomForestClassifier(n_estimators=300,
                             max_depth=None,
                             random_state=42)
clf.fit(Xtr, ytr)

# 5) Avaliação rápida
y_pred = clf.predict(Xte)
print("\nAcurácia :", accuracy_score(yte, y_pred))
print("Matriz de confusão :\n", confusion_matrix(yte, y_pred))
print("\nRelatório :\n", classification_report(yte, y_pred, zero_division=0))

# 6) Salva modelo
joblib.dump(clf, "risk_model.pkl")
print("\nModelo salvo em  risk_model.pkl")
