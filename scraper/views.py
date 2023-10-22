from ECA_CPI_Scraper.settings import MEDIA_ROOT
from scraper.models import Country, Data
from django.shortcuts import render
from django.views.generic import ListView, DetailView
from django.http import HttpResponse
from .utils import render_to_pdf, scrape_pdf, report
from django.core.files.base import ContentFile, File
from django.core.files.temp import NamedTemporaryFile
import pandas as pd
import os
import io
from django.contrib import messages
from io import BytesIO

from docx2pdf import convert

import subprocess

try:
    from comtypes import client
except ImportError:
    client = None

def doc2pdf(doc,path):
    """
    convert a doc/docx document to pdf format
    :param doc: path to document
    """
    doc = os.path.abspath(doc) # bugfix - searching files in windows/system32
    if client is None:
        return doc2pdf_linux(doc,path)
    name, ext = os.path.splitext(doc)
    try:
        word = client.CreateObject('Word.Application')
        worddoc = word.Documents.Open(doc)
        worddoc.SaveAs(name + '.pdf', FileFormat=17)
    except Exception:
        raise
    finally:
        worddoc.Close()
        word.Quit()


def doc2pdf_linux(doc,path):
    """
    convert a doc/docx document to pdf format (linux only, requires libreoffice)
    :param doc: path to document
    """
    cmd = 'libreoffice --convert-to pdf'.split() + [doc]
    p = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE,cwd=path)
    p.wait(timeout=10)
    stdout, stderr = p.communicate()
    if stderr:
        raise subprocess.SubprocessError(stderr)


def home_view(request):
    hello = "Hello world from Eyaya"
    context = {"H": hello}
    return render(request, 'scraper/home.html', context)
  

class CountryListView(ListView):
    model = Country
    template_name = 'scraper/country_list.html'


def country_detail_view(request, pk):
    country = Country.objects.get(pk=pk)
    data = Data()
    data.country = country
    d = render_to_pdf(country)

    if d:
        path, pdf, c_site, c_check_and, c_check_or, msg, full_path = d
        name = data.country.name
        
        r_path = os.path.join(MEDIA_ROOT, 'Data', name)
        
        messages.success(request, msg)
        pdf_temp = NamedTemporaryFile(delete=True)
        pdf_temp.write(pdf.content)
        pdf_temp.flush()
        country.site = c_site
        country.check_and = c_check_and
        country.check_or = c_check_or
        if name == 'Niger' or name == 'Benin':
            data.CPI_doc.save(path, File(pdf_temp),  save=True)
            data.save_doc()
            doc2pdf(full_path,r_path)

            filename, file_extension = os.path.splitext(full_path)
            f = open(filename+'.pdf', 'rb')
            os.remove(filename+'.pdf')
            path = path.replace('docx','pdf')
            data.CPI_pdf.save(path, File(f),  save=True)
            f.close()
            data.save_doc()
        else:
            data.CPI_pdf.save(path, File(pdf_temp),  save=True)
            data.save_pdf()

    ex = scrape_pdf(country)
    if ex:
        print('Scrapping...')
        path, pdf_path, exl = ex
        #messages.success(request, msg)
        filename, file_extension = os.path.splitext(pdf_path)
        exl_temp = exl
        output = io.BytesIO()

        # Use the StringIO object as the filehandle.
        writer = pd.ExcelWriter(output, engine='xlsxwriter')

        # Write the data frame to the StringIO object.
        exl_temp.to_excel(writer, sheet_name=filename, index=False)
        writer.save()
        output.seek(0)
        
        data_obj = Data.objects.get(pdf_Filename='CPI_'+pdf_path)
        data_obj.CPI_excel.save(path, File(output), save=True)
        data_obj.save_excel()
    #Data.objects.all().order_by('-id')
    '''
    r = report(country)
    if r:
        re, pdf_full_path, report_file = r
        #messages.success(request, msg)
        filename, file_extension = os.path.splitext(report_file)
        report_temp = re
        output = io.BytesIO()

        # Use the StringIO object as the filehandle.
        writer = pd.ExcelWriter(output, engine='xlsxwriter')

        # Write the data frame to the StringIO object.
        report_temp.to_excel(writer, sheet_name=filename)
        writer.save()
        output.seek(0)
        
        data_obj = Data.objects.get(pdf_Filename='CPI_' + pdf_full_path)
        data_obj.report_excel.save(report_file, File(output), save=True)
        data_obj.save_report()
    '''
    country.save()
    context = {'country': country}
    

    return render(request, 'scraper/country_detail.html', context)
