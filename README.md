# backend Vitrine HUBIS

Instalar dependências:

```
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Resetar somente produtos (preserva empresas e usuarios):

```
python reset_products_only.py
```

Resetar e popular produtos fake novamente:

```
python reset_products_only.py --seed
```

Executar

```
python app.py
```
