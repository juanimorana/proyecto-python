import pandas as pd
from borb.pdf.document.document import Document
from borb.pdf.page.page import Page
from borb.pdf.canvas.layout.page_layout.multi_column_layout import SingleColumnLayout
from borb.pdf.canvas.layout.table.table import Table, TableCell
from borb.pdf.canvas.layout.text.paragraph import Paragraph
from borb.pdf.pdf import PDF

def generar_datos_csv():
    """Genera un archivo CSV de prueba a partir de un diccionario."""
    data = {
        "personas": [
            {"nombre": "Ana", "edad": 30, "email": "ana@gmail.com"},
            {"nombre": "Luis", "edad": 25, "email": "luis@gmail.com"},
            {"nombre": "Marta", "edad": 40, "email": "marta@gmail.com"}
        ]
    }
    df = pd.DataFrame(data["personas"])
    df.to_csv("personas.csv", index=False)
    print("Archivo CSV generado: personas.csv")

def filtrar_mayores(archivo_entrada, archivo_salida):
    """Filtra personas mayores de 30 años y guarda un nuevo CSV."""
    df = pd.read_csv(archivo_entrada)
    mayores = df[df["edad"] > 30]
    mayores.to_csv(archivo_salida, index=False)
    print(f"Archivo filtrado generado: {archivo_salida}")

def exportar_csv_a_pdf(archivo_csv, archivo_pdf):
    """Lee un CSV y genera un PDF con una tabla usando Borb."""
    df = pd.read_csv(archivo_csv)
    
    doc = Document()
    page = Page()
    doc.add_page(page)
    layout = SingleColumnLayout(page)
    
    tabla = Table(number_of_rows=len(df) + 1, number_of_columns=len(df.columns))
    
    for col in df.columns:
        tabla.add(TableCell(Paragraph(col.capitalize())))
        
    for index, row in df.iterrows():
        for value in row:
            tabla.add(Paragraph(str(value)))
            
    layout.add(tabla)
    
    with open(archivo_pdf, "wb") as pdf_file:
        PDF.dumps(pdf_file, doc)
    print(f"Archivo PDF generado: {archivo_pdf}")

if __name__ == "__main__":
    generar_datos_csv()
    
    filtrar_mayores("personas.csv", "mayores_de_30.csv")
    
    exportar_csv_a_pdf("personas.csv", "personas_borb.pdf")