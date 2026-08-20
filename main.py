"""
Projeto FLL - Identificador de Abelhas por QR Code
Equipe Avatron
----------------------------------------------------
Lê um QR code pela webcam (colado num card em frente à câmera) e mostra
na tela as informações da espécie de abelha correspondente.

Como funciona:
1. A webcam captura o vídeo continuamente.
2. Cada frame é analisado em busca de QR codes usando o leitor nativo
   do OpenCV (cv2.QRCodeDetector) - não depende de nenhuma DLL externa,
   o que evita problemas de instalação em PCs de laboratório/escola.
3. Quando um QR code válido é detectado, a chave lida (ex: "jatai") é
   usada para buscar os dados da espécie em abelhas.json.
4. A interface (Tkinter) atualiza mostrando nome, espécie, características
   e curiosidade da abelha, em cards com ícone.

Requisitos:
    pip install opencv-python pillow

Uso:
    python3 main.py
"""

import json
import time
import tkinter as tk

import cv2
from PIL import Image, ImageTk

CAMINHO_DB = "abelhas.json"
INDICE_CAMERA = 0          # troque para 1, 2... se tiver mais de uma câmera
TEMPO_MANTER_INFO = 3.0    # segundos que a info fica na tela após perder o QR

# ---------------------------------------------------------------------------
# Paleta de cores - extraída da logo da equipe Avatron
# ---------------------------------------------------------------------------
COR_FUNDO = "#180F30"          # roxo bem escuro (fundo geral da janela)
COR_PAINEL = "#2C1B54"         # roxo escuro (fundo do painel de info)
COR_CARD = "#3E2670"           # roxo médio (fundo de cada card de campo)
COR_CARD_BORDA = "#5B3B9E"     # roxo mais claro (borda/realce dos cards)
COR_CREME = "#F3E9D2"          # creme (títulos, texto de destaque)
COR_TEAL = "#2FA3A3"           # teal (detalhe/linha divisória)
COR_TEXTO = "#E7E0F5"          # lilás bem claro (texto de corpo, boa leitura)
COR_TEXTO_SECUNDARIO = "#B7A6DE"  # lilás acinzentado (nome científico, labels)

FONTE_TITULO = ("Century Gothic", 22, "bold")
FONTE_CIENTIFICO = ("Century Gothic", 13, "italic")
FONTE_ROTULO = ("Century Gothic", 10, "bold")
FONTE_VALOR = ("Century Gothic", 12)
FONTE_MARCA = ("Century Gothic", 16, "bold")

ICONES = {
    "porte": "📏",
    "ferrao": "🐝",
    "habitat": "🌳",
    "importancia": "🌼",
    "curiosidade": "💡",
}


def arredondar_retangulo(canvas, x1, y1, x2, y2, raio=18, **kwargs):
    """Desenha um retângulo de cantos arredondados num Canvas do Tkinter.

    O Tkinter não tem um "card arredondado" pronto, então isso é feito
    desenhando um polígono suavizado (smooth=True) passando pelos cantos.
    """
    pontos = [
        x1 + raio, y1,
        x2 - raio, y1,
        x2, y1,
        x2, y1 + raio,
        x2, y2 - raio,
        x2, y2,
        x2 - raio, y2,
        x1 + raio, y2,
        x1, y2,
        x1, y2 - raio,
        x1, y1 + raio,
        x1, y1,
    ]
    return canvas.create_polygon(pontos, smooth=True, **kwargs)


class AppAbelhas:
    def __init__(self, root):
        self.root = root
        self.root.title("Identificador de Abelhas - Avatron")
        self.root.configure(bg=COR_FUNDO)

        self.abelhas = self._carregar_banco()

        self.ultima_deteccao = None      # chave da última abelha detectada
        self.hora_ultima_deteccao = 0    # timestamp da última leitura válida

        # Detector de QR code nativo do OpenCV (não usa nenhuma DLL externa)
        self.detector_qr = cv2.QRCodeDetector()

        self._montar_interface()

        self.cap = cv2.VideoCapture(INDICE_CAMERA)
        if not self.cap.isOpened():
            raise RuntimeError(
                f"Não consegui abrir a câmera de índice {INDICE_CAMERA}. "
                "Verifique se ela está conectada ou troque INDICE_CAMERA."
            )

        self._atualizar_frame()

    def _carregar_banco(self):
        with open(CAMINHO_DB, encoding="utf-8") as f:
            return json.load(f)

    # ------------------------------------------------------------------
    # Montagem da interface
    # ------------------------------------------------------------------
    def _montar_interface(self):
        """Janela dividida: câmera à esquerda, info da abelha à direita."""
        container = tk.Frame(self.root, bg=COR_FUNDO)
        container.pack(fill="both", expand=True, padx=14, pady=14)

        # --- Lado esquerdo: vídeo da câmera ---
        lado_esquerdo = tk.Frame(container, bg=COR_FUNDO)
        lado_esquerdo.grid(row=0, column=0, padx=(0, 14), sticky="n")

        tk.Label(
            lado_esquerdo, text="🐝  AVATRON", font=FONTE_MARCA,
            fg=COR_CREME, bg=COR_FUNDO,
        ).pack(anchor="w", pady=(0, 8))

        self.label_video = tk.Label(lado_esquerdo, bg="#000000",
                                     highlightbackground=COR_TEAL,
                                     highlightthickness=2)
        self.label_video.pack()

        # --- Lado direito: painel de informações ---
        painel = tk.Frame(container, bg=COR_PAINEL, width=400, height=520)
        painel.grid(row=0, column=1, sticky="n")
        painel.grid_propagate(False)

        # Faixa colorida no topo do painel (detalhe de marca)
        faixa = tk.Frame(painel, bg=COR_TEAL, height=6)
        faixa.pack(fill="x", side="top")

        self.lbl_titulo = tk.Label(
            painel, text="Aponte um card\npara a câmera",
            font=FONTE_TITULO, fg=COR_CREME, bg=COR_PAINEL,
            wraplength=360, justify="left",
        )
        self.lbl_titulo.pack(anchor="w", padx=20, pady=(20, 4))

        self.lbl_cientifico = tk.Label(
            painel, text="", font=FONTE_CIENTIFICO,
            fg=COR_TEXTO_SECUNDARIO, bg=COR_PAINEL,
            wraplength=360, justify="left",
        )
        self.lbl_cientifico.pack(anchor="w", padx=20, pady=(0, 14))

        area_cards = tk.Frame(painel, bg=COR_PAINEL)
        area_cards.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        self.campos = {}
        for chave, rotulo in [
            ("porte", "Porte"),
            ("ferrao", "Ferrão"),
            ("habitat", "Habitat"),
            ("importancia", "Importância"),
            ("curiosidade", "Curiosidade"),
        ]:
            self.campos[chave] = self._criar_card(area_cards, rotulo, ICONES[chave])

    def _criar_card(self, pai, rotulo, icone):
        """Cria um 'card' com cantos arredondados para um campo de informação.

        Retorna um dicionário com o Canvas e o id do texto que deve ser
        atualizado quando os dados da abelha mudarem.
        """
        canvas = tk.Canvas(pai, bg=COR_PAINEL, highlightthickness=0,
                            height=76)
        canvas.pack(fill="x", pady=5)

        def desenhar(_event=None):
            canvas.delete("fundo")
            largura = canvas.winfo_width() or 360
            arredondar_retangulo(
                canvas, 2, 2, largura - 2, 74, raio=16,
                fill=COR_CARD, outline=COR_CARD_BORDA, width=1, tags="fundo",
            )
            canvas.tag_lower("fundo")

        canvas.bind("<Configure>", desenhar)

        canvas.create_text(
            16, 16, anchor="nw", text=f"{icone}  {rotulo.upper()}",
            font=FONTE_ROTULO, fill=COR_TEAL,
        )
        id_texto = canvas.create_text(
            16, 38, anchor="nw", text="", font=FONTE_VALOR,
            fill=COR_TEXTO, width=340,
        )
        return {"canvas": canvas, "id_texto": id_texto}

    # ------------------------------------------------------------------
    # Loop de câmera / detecção
    # ------------------------------------------------------------------
    def _atualizar_frame(self):
        ok, frame = self.cap.read()
        if ok:
            self._processar_qrcode(frame)

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            imagem = Image.fromarray(frame_rgb)
            imagem_tk = ImageTk.PhotoImage(image=imagem)
            self.label_video.imgtk = imagem_tk
            self.label_video.configure(image=imagem_tk)

        if (self.ultima_deteccao is not None
                and time.time() - self.hora_ultima_deteccao > TEMPO_MANTER_INFO):
            self._mostrar_aguardando()
            self.ultima_deteccao = None

        self.root.after(30, self._atualizar_frame)

    def _processar_qrcode(self, frame):
        # detectAndDecodeMulti retorna: (achou_algo, textos, pontos, retificado)
        # "pontos" traz os 4 cantos de cada QR code encontrado no frame.
        ok, textos, pontos, _ = self.detector_qr.detectAndDecodeMulti(frame)
        if not ok:
            return

        for texto, cantos in zip(textos, pontos):
            chave = texto.strip()
            if not chave:
                continue  # QR code presente mas não decodificado ainda

            # Desenha um contorno ao redor do QR code detectado
            cantos_int = cantos.astype(int)
            x, y = cantos_int[0]

            if chave in self.abelhas:
                cv2.polylines(frame, [cantos_int], True, (0, 255, 0), 3)
                self.hora_ultima_deteccao = time.time()
                if chave != self.ultima_deteccao:
                    self.ultima_deteccao = chave
                    self._mostrar_abelha(chave)
            else:
                cv2.polylines(frame, [cantos_int], True, (0, 0, 255), 3)
                cv2.putText(
                    frame, "QR nao cadastrado", (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2,
                )

    # ------------------------------------------------------------------
    # Atualização do painel
    # ------------------------------------------------------------------
    def _mostrar_abelha(self, chave):
        dados = self.abelhas[chave]
        self.lbl_titulo.configure(text=dados["nome_popular"])
        self.lbl_cientifico.configure(text=dados["nome_cientifico"])
        for campo, card in self.campos.items():
            texto = dados.get(campo, "-")
            card["canvas"].itemconfig(card["id_texto"], text=texto)

    def _mostrar_aguardando(self):
        self.lbl_titulo.configure(text="Aponte um card\npara a câmera")
        self.lbl_cientifico.configure(text="")
        for card in self.campos.values():
            card["canvas"].itemconfig(card["id_texto"], text="")

    def fechar(self):
        if self.cap.isOpened():
            self.cap.release()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = AppAbelhas(root)
    root.protocol("WM_DELETE_WINDOW", app.fechar)
    root.mainloop()
