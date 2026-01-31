import sys
import win32ui

PRINTER_NAME = "Brother QL-810W"  # ajuste se o nome for outro

def center_text(dc, y, text):
    width = dc.GetDeviceCaps(8)   # largura imprimível
    w, h = dc.GetTextExtent(text)
    x = max(0, (width - w) // 2)
    dc.TextOut(x, y, text)
    return h

def main():
    # Uso:
    # python imprimir_lote.py "Nome do Folheto" 1000 5
    if len(sys.argv) < 4:
        print('Uso: python imprimir_lote.py "Nome do Folheto" 1000 5')
        sys.exit(1)

    nome = sys.argv[1]
    quantidade = sys.argv[2]
    total_pacotes = int(sys.argv[3])

    dc = win32ui.CreateDC()
    dc.CreatePrinterDC(PRINTER_NAME)

    altura_etiqueta = dc.GetDeviceCaps(10)

    # Altura total da etiqueta (para o rodapé)
    altura_total = dc.GetDeviceCaps(10)

    # Fontes GRANDES para 62mm
    fonte_nome = win32ui.CreateFont({"name": "Arial", "height": 90, "weight": 800})
    fonte_quantidade = win32ui.CreateFont({"name": "Arial", "height": 160, "weight": 900})
    fonte_pacote = win32ui.CreateFont({"name": "Arial", "height": 70, "weight": 800})

    # Espaçamentos para 62mm
    margem_topo = 30
    espaco_entre = 20
    margem_base = 40

    # ✅ UM ÚNICO JOB (um StartDoc só)
    dc.StartDoc("Lote 62x100")
    try:
        for i in range(1, total_pacotes + 1):
            pacote_txt = f"{i}/{total_pacotes}"

            dc.StartPage()

            # Nome
            dc.SelectObject(fonte_nome)
            y_nome = margem_topo
            h_nome = center_text(dc, y_nome, nome)

            # Quantidade
            dc.SelectObject(fonte_quantidade)
            y_quantidade = y_nome + h_nome + espaco_entre
            center_text(dc, y_quantidade, str(quantidade))

            # Pacote (ancorado embaixo)
            dc.SelectObject(fonte_pacote)
            _, h_pacote = dc.GetTextExtent(pacote_txt)
            y_pacote = max(0, altura_total - margem_base - h_pacote)
            center_text(dc, y_pacote, pacote_txt)

            dc.EndPage()

        # ✅ EndDoc só no final = fim do job (driver tende a cortar aqui)
        dc.EndDoc()
    finally:
        dc.DeleteDC()

    print(f"Lote enviado: {total_pacotes} etiquetas em 62mm")

if __name__ == "__main__":
    main()
