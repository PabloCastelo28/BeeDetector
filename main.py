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
import os
import time
import tkinter as tk

import cv2
from PIL import Image, ImageOps, ImageTk

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

TAMANHO_FOTO = 130  # tamanho (em pixels) do quadro de foto da abelha, lado a lado com o nome


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

        self._foto_referencia = None  # evita que a foto suma (garbage collector)

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
        # A largura é travada em 460px (fica alinhado visualmente com o
        # vídeo da câmera), mas a ALTURA cresce livremente conforme o
        # conteúdo - assim nenhum texto fica cortado, mesmo com abelhas
        # que tenham descrições mais longas.
        painel = tk.Frame(container, bg=COR_PAINEL)
        painel.grid(row=0, column=1, sticky="n")

        # Spacer invisível: só existe para forçar a largura mínima do
        # painel, sem interferir na altura (que fica livre).
        tk.Frame(painel, width=460, height=1, bg=COR_PAINEL).pack()

        # Faixa colorida no topo do painel (detalhe de marca)
        faixa = tk.Frame(painel, bg=COR_TEAL, height=6)
        faixa.pack(fill="x", side="top")

        # --- Cabeçalho: nome/científico à esquerda, foto à direita ---
        cabecalho = tk.Frame(painel, bg=COR_PAINEL)
        cabecalho.pack(fill="x", padx=20, pady=(20, 10))

        coluna_texto = tk.Frame(cabecalho, bg=COR_PAINEL)
        coluna_texto.pack(side="left", fill="both", expand=True)

        self.lbl_titulo = tk.Label(
            coluna_texto, text="Aponte um\ncard para\na câmera",
            font=FONTE_TITULO, fg=COR_CREME, bg=COR_PAINEL,
            wraplength=270, justify="left",
        )
        self.lbl_titulo.pack(anchor="w")

        self.lbl_cientifico = tk.Label(
            coluna_texto, text="", font=FONTE_CIENTIFICO,
            fg=COR_TEXTO_SECUNDARIO, bg=COR_PAINEL,
            wraplength=270, justify="left",
        )
        self.lbl_cientifico.pack(anchor="w", pady=(4, 0))

        self.foto = self._criar_area_foto(cabecalho)
        self.foto["canvas"].pack(side="right", padx=(10, 0))

        area_cards = tk.Frame(painel, bg=COR_PAINEL)
        area_cards.pack(fill="both", expand=True, padx=14, pady=(4, 14))

        self.campos = {}
        for chave, rotulo in [
            ("porte", "Porte"),
            ("ferrao", "Ferrão"),
            ("habitat", "Habitat"),
            ("importancia", "Importância"),
            ("curiosidade", "Curiosidade"),
        ]:
            self.campos[chave] = self._criar_card(area_cards, rotulo, ICONES[chave])

    def _criar_area_foto(self, pai):
        """Cria o quadro (com cantos arredondados) onde a foto da abelha
        aparece, ao lado do nome. Enquanto não há foto disponível para a
        espécie, mostra um ícone de abelha como placeholder.
        """
        canvas = tk.Canvas(
            pai, width=TAMANHO_FOTO, height=TAMANHO_FOTO,
            bg=COR_PAINEL, highlightthickness=0,
        )
        arredondar_retangulo(
            canvas, 2, 2, TAMANHO_FOTO - 2, TAMANHO_FOTO - 2, raio=16,
            fill=COR_CARD, outline=COR_CARD_BORDA, width=1, tags="fundo_foto",
        )
        id_placeholder = canvas.create_text(
            TAMANHO_FOTO / 2, TAMANHO_FOTO / 2,
            text="🐝\nsem foto", font=("Century Gothic", 11),
            fill=COR_TEXTO_SECUNDARIO, justify="center",
        )
        return {"canvas": canvas, "id_placeholder": id_placeholder, "id_imagem": None}

    def _criar_card(self, pai, rotulo, icone):
        """Cria um 'card' com cantos arredondados para um campo de informação.

        A altura do card se ajusta automaticamente ao tamanho do texto
        (recalculada toda vez que o conteúdo muda), então textos longos
        como "importância" ou "curiosidade" nunca ficam cortados.

        Retorna um dicionário com o Canvas, o id do texto e a função de
        redesenho, que devem ser usados para atualizar o card.
        """
        canvas = tk.Canvas(pai, bg=COR_PAINEL, highlightthickness=0, height=70)
        canvas.pack(fill="x", pady=6)

        canvas.create_text(
            16, 14, anchor="nw", text=f"{icone}  {rotulo.upper()}",
            font=FONTE_ROTULO, fill=COR_TEAL,
        )
        id_texto = canvas.create_text(
            16, 38, anchor="nw", text="", font=FONTE_VALOR, fill=COR_TEXTO,
        )

        def redesenhar(_event=None):
            largura = canvas.winfo_width() or 400
            largura_texto = max(largura - 32, 60)
            canvas.itemconfig(id_texto, width=largura_texto)

            caixa_texto = canvas.bbox(id_texto)
            altura_texto = (caixa_texto[3] - caixa_texto[1]) if caixa_texto else 18
            altura_total = max(38 + altura_texto + 16, 70)

            canvas.configure(height=altura_total)
            canvas.delete("fundo")
            arredondar_retangulo(
                canvas, 2, 2, largura - 2, altura_total - 2, raio=16,
                fill=COR_CARD, outline=COR_CARD_BORDA, width=1, tags="fundo",
            )
            canvas.tag_lower("fundo")

        canvas.bind("<Configure>", redesenhar)
        return {"canvas": canvas, "id_texto": id_texto, "redesenhar": redesenhar}

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
            card["redesenhar"]()
        self._atualizar_foto(dados.get("foto"))

    def _mostrar_aguardando(self):
        self.lbl_titulo.configure(text="Aponte um\ncard para\na câmera")
        self.lbl_cientifico.configure(text="")
        for card in self.campos.values():
            card["canvas"].itemconfig(card["id_texto"], text="")
            card["redesenhar"]()
        self._atualizar_foto(None)

    def _atualizar_foto(self, caminho):
        """Troca a imagem exibida no quadro de foto.

        Para adicionar/trocar a foto de uma espécie, basta editar o campo
        "foto" dela em abelhas.json apontando para o caminho do arquivo
        (ex: "fotos/jatai.jpg"). Se o campo estiver vazio ou o arquivo não
        existir, mostra um ícone de abelha no lugar, sem quebrar o programa.
        """
        canvas = self.foto["canvas"]

        if self.foto["id_imagem"] is not None:
            canvas.delete(self.foto["id_imagem"])
            self.foto["id_imagem"] = None

        if caminho and os.path.exists(caminho):
            try:
                interno = TAMANHO_FOTO - 8  # deixa uma margem dentro da borda
                imagem = Image.open(caminho).convert("RGB")
                # ImageOps.fit recorta e redimensiona preenchendo o quadrado
                # todo, sem distorcer a proporção da foto original.
                imagem = ImageOps.fit(imagem, (interno, interno), Image.LANCZOS)
                foto_tk = ImageTk.PhotoImage(imagem)
                self._foto_referencia = foto_tk  # evita garbage collection
                self.foto["id_imagem"] = canvas.create_image(
                    TAMANHO_FOTO / 2, TAMANHO_FOTO / 2, image=foto_tk,
                )
                canvas.itemconfig(self.foto["id_placeholder"], state="hidden")
                return
            except Exception:
                pass  # se o arquivo estiver corrompido, cai no placeholder

        canvas.itemconfig(
            self.foto["id_placeholder"], state="normal", text="🐝\nsem foto",
        )

    def fechar(self):
        if self.cap.isOpened():
            self.cap.release()
        self.root.destroy()


if __name__ == "__main__":
    # Mude para False se quiser testar numa janela normal (mais fácil de
    # depurar). Deixe True para a apresentação final / competição.
    MODO_TELA_CHEIA = True

    root = tk.Tk()
    app = AppAbelhas(root)
    root.protocol("WM_DELETE_WINDOW", app.fechar)

    if MODO_TELA_CHEIA:
        root.attributes("-fullscreen", True)
        # ESC sai do modo tela cheia - útil durante testes na própria Pi,
        # sem precisar reiniciar o programa toda vez.
        root.bind("<Escape>", lambda e: root.attributes("-fullscreen", False))

    root.mainloop()
