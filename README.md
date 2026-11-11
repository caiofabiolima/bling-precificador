# Precificador Bling -> Loja Integrada Varejo

Le os produtos vinculados a loja Varejo no Bling, calcula o preco de varejo e grava de volta.

- Promocional = preco base (atacado) + 30%, arredondado para cima no final ,90
- Cheio = promocional + 15%, arredondado para cima no final ,90
- Porcentagens e final do preco editaveis na tela

## Instalar em uma maquina nova

1. Instale o Python 3.10+.
2. `git clone <url-do-repo>` e entre na pasta.
3. Copie `.env.example` para `.env` e cole o Client ID e o Client Secret do app no Bling
   (Central de Extensoes > Area do Integrador). Esses dois NAO ficam no repositorio.
4. O link de redirecionamento do app no Bling deve ser `http://localhost:8080/callback`.
5. Rode `python bling.py auth` e autorize no navegador. Isso cria o `tokens.json` desta maquina.
   Nao copie o `tokens.json` de outra maquina: o Bling troca o token a cada renovacao e duas
   maquinas com o mesmo token se derrubam.
6. Abra `app\abrir.bat` (ou `python app\app.py`). A tela abre em http://127.0.0.1:8765.

## Fluxo

1. Exportar o produto para a loja (no Bling, carrinho verde).
2. "Ler produtos e simular" -> conferir -> "Gravar no Bling" (salva backup antes).
3. Sincronizar o preco da loja (no Bling).

"Restaurar" volta os precos de um backup em `app/backups/`.
