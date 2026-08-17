"""
Gera um QR code PNG para cada espécie de abelha cadastrada em abelhas.json.
Cada QR code contém apenas a CHAVE da espécie (ex: "jatai"), não os dados
completos — isso deixa o QR code mais simples de ler e mantém os dados
detalhados só no arquivo local, fácil de editar depois.

Uso:
    python3 gerar_qrcodes.py

Saída:
    Uma pasta "qrcodes_gerados/" com um PNG por espécie, pronta pra imprimir
    e colar nos cards.
"""

import json
import os
import qrcode

PASTA_SAIDA = "qrcodes_gerados"


def gerar_qrcodes():
    with open("abelhas.json", encoding="utf-8") as f:
        abelhas = json.load(f)

    os.makedirs(PASTA_SAIDA, exist_ok=True)

    for chave, dados in abelhas.items():
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        # O conteúdo do QR code é só a chave (ex: "jatai").
        # O programa principal usa essa chave para buscar os dados no JSON.
        qr.add_data(chave)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        caminho = os.path.join(PASTA_SAIDA, f"{chave}.png")
        img.save(caminho)
        print(f"Gerado: {caminho}  (conteúdo: '{chave}' -> {dados['nome_popular']})")

    print(f"\nPronto! {len(abelhas)} QR codes gerados em '{PASTA_SAIDA}/'.")
    print("Imprima cada um e cole em um card junto com foto/nome da espécie.")


if __name__ == "__main__":
    gerar_qrcodes()
