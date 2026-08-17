"""
Projeto FLL - Identificador de Abelhas por QR Code
----------------------------------------------------
Lê um QR code pela webcam (colado num card em frente à câmera) e mostra
na tela as informações da espécie de abelha correspondente.

Como funciona:
1. A webcam captura o vídeo continuamente.
2. Cada frame é analisado em busca de QR codes (pyzbar).
3. Quando um QR code válido é detectado, a chave lida (ex: "jatai") é
   usada para buscar os dados da espécie em abelhas.json.
4. A interface (Tkinter) atualiza mostrando nome, espécie, características
   e curiosidade da abelha.

Requisitos:
    pip install opencv-python pyzbar pillow

Uso:
    python3 main.py
"""

import json
import time
import tkinter as tk

import cv2
from PIL import Image, ImageTk
from pyzbar import pyzbar

CAMINHO_DB = "abelhas.json"
INDICE_CAMERA = 0          # troque para 1, 2... se tiver mais de uma câmera
TEMPO_MANTER_INFO = 3.0    # segundos que a info fica na tela após perder o QR


class AppAbelhas:
    def __init__(self, root):
        self.root = root
        self.root.title("Identificador de Abelhas - FLL")
        self.root.configure(bg="#1c1c1c")

        self.abelhas = self._carregar_banco()

        self.ultima_deteccao = None      # chave da última abelha detectada
        self.hora_ultima_deteccao = 0    # timestamp da última leitura válida

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

    def _montar_interface(self):
        """Janela dividida: câmera à esquerda, info da abelha à direita."""
        container = tk.Frame(self.root, bg="#1c1c1c")
        container.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Lado esquerdo: vídeo da câmera ---
        self.label_video = tk.Label(container, bg="#000000")
        self.label_video.grid(row=0, column=0, padx=(0, 10))

        # --- Lado direito: painel de informações ---
        painel = tk.Frame(container, bg="#2b2b2b", width=380, height=480)
        painel.grid(row=0, column=1, sticky="n")
        painel.grid_propagate(False)

        self.lbl_titulo = tk.Label(
            painel, text="Aponte um card para a câmera",
            font=("Helvetica", 18, "bold"), fg="#f5c542", bg="#2b2b2b",
            wraplength=340, justify="left",
        )
        self.lbl_titulo.pack(anchor="w", padx=15, pady=(20, 5))

        self.lbl_cientifico = tk.Label(
            painel, text="", font=("Helvetica", 13, "italic"),
            fg="#cccccc", bg="#2b2b2b", wraplength=340, justify="left",
        )
        self.lbl_cientifico.pack(anchor="w", padx=15, pady=(0, 15))

        self.campos = {}
        for chave, rotulo in [
            ("porte", "Porte"),
            ("ferrao", "Ferrão"),
            ("habitat", "Habitat"),
            ("importancia", "Importância"),
            ("curiosidade", "Curiosidade"),
        ]:
            bloco = tk.Frame(painel, bg="#2b2b2b")
            bloco.pack(anchor="w", padx=15, pady=6, fill="x")

            tk.Label(
                bloco, text=rotulo.upper(), font=("Helvetica", 10, "bold"),
                fg="#f5c542", bg="#2b2b2b",
            ).pack(anchor="w")

            lbl_valor = tk.Label(
                bloco, text="", font=("Helvetica", 12), fg="#ffffff",
                bg="#2b2b2b", wraplength=340, justify="left",
            )
            lbl_valor.pack(anchor="w")
            self.campos[chave] = lbl_valor

    def _atualizar_frame(self):
        ok, frame = self.cap.read()
        if ok:
            self._processar_qrcode(frame)

            # Converte o frame do OpenCV (BGR) para exibir no Tkinter (RGB)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            imagem = Image.fromarray(frame_rgb)
            imagem_tk = ImageTk.PhotoImage(image=imagem)
            self.label_video.imgtk = imagem_tk  # evita garbage collection
            self.label_video.configure(image=imagem_tk)

        # Se não detecta nada há muito tempo, limpa o painel
        if (self.ultima_deteccao is not None
                and time.time() - self.hora_ultima_deteccao > TEMPO_MANTER_INFO):
            self._mostrar_aguardando()
            self.ultima_deteccao = None

        self.root.after(30, self._atualizar_frame)  # ~30fps

    def _processar_qrcode(self, frame):
        codigos = pyzbar.decode(frame)
        for codigo in codigos:
            chave = codigo.data.decode("utf-8").strip()

            # Desenha um retângulo verde ao redor do QR code detectado
            (x, y, w, h) = codigo.rect
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 3)

            if chave in self.abelhas:
                self.hora_ultima_deteccao = time.time()
                if chave != self.ultima_deteccao:
                    self.ultima_deteccao = chave
                    self._mostrar_abelha(chave)
            else:
                cv2.putText(
                    frame, "QR nao cadastrado", (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2,
                )

    def _mostrar_abelha(self, chave):
        dados = self.abelhas[chave]
        self.lbl_titulo.configure(text=dados["nome_popular"])
        self.lbl_cientifico.configure(text=dados["nome_cientifico"])
        for campo, label in self.campos.items():
            label.configure(text=dados.get(campo, "-"))

    def _mostrar_aguardando(self):
        self.lbl_titulo.configure(text="Aponte um card para a câmera")
        self.lbl_cientifico.configure(text="")
        for label in self.campos.values():
            label.configure(text="")

    def fechar(self):
        if self.cap.isOpened():
            self.cap.release()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = AppAbelhas(root)
    root.protocol("WM_DELETE_WINDOW", app.fechar)
    root.mainloop()
