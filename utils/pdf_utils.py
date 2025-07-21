from xhtml2pdf import pisa

def html_to_pdf(html_content, output_path):
    """
    Convertit du HTML en PDF avec xhtml2pdf.
    """
    with open(output_path, "w+b") as result_file:
        pisa_status = pisa.CreatePDF(src=html_content, dest=result_file)
        return not pisa_status.err