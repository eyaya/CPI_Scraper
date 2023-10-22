from ECA_CPI_Scraper.settings import MEDIA_ROOT
import requests
from bs4 import BeautifulSoup
import os
import datetime
import re
import time
import urllib.request
from urllib.request import unquote

from urllib.parse import urlparse, urljoin
import pandas as pd

import pdfplumber as pp
import camelot

import numpy as np

from PyPDF2 import PdfFileReader
import numpy as np
import subprocess

try:
    from comtypes import client
except ImportError:
    client = None





Months = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
          'september', 'october', 'november', 'december']
months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
Monthsf = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août ', 'septembre', 'octobre', 'novembre', 'décembre ']
monthsf=['janv', 'févr', 'mars', 'avr', 'mai', 'juin', 'juillet', 'aout', 'sept', 'oct', 'nov', 'dec'] #'févr'
months_number = ['01','02','03','04','05','06','07','08','09','10','11','12']
dt = datetime.datetime.now()
mn = dt.month # Today's Month Number
print(mn)
M = Months[mn - 2]  # long month format eg January
m = months[mn - 2]  # short month format eg Jan
Mf = Monthsf[mn - 2]  # french long month format eg Janvier
mf = monthsf[mn - 2]  # french short month format eg Janv
Mn = months_number[mn - 2]  # Month Number eq 01
y = dt.year         # Year eg 2021
yn = str(y)[-2:]    # Short year format like 21
print(mf, y)

# Create your views here.
sites = {
    'Benin': 'https://insae.bj/publications/publications-mensuelles/prix',
    'Botswana': 'https://www.statsbots.org.bw/publication-by-sector/111',
    'Kenya': 'https://www.knbs.or.ke/?page_id=1591',
    'Burkina_Faso': 'http://www.insd.bf/index.php/publications?id=45',
    'Burundi': 'https://www.isteebu.bi/icp/',
    'Cote_dIvoire': f'http://www.ins.ci/templates/ihpc/ihpc{Mn}{yn}.pdf',
    'Gambia': 'https://www.gbosdata.org/downloads/cpi-2021',
    'Guinee': 'https://www.stat-guinee.org/index.php/publications-ins/publications-infra-annuelles/ihpc',
    'Uganda': 'https://www.ubos.org/?pagename=explore-publications&p_id=107',
    'South_Africa': f'http://www.statssa.gov.za/?page_id=1854&PPN=P0141&SCH=7272{mn}',
    'Ghana': 'https://www.statsghana.gov.gh/nationalaccount_macros.php?Stats=MTE2MTIyMjQ5Ni41NjY=/webstats/7163p83s71',
    'Tanzania': f'https://www.nbs.go.tz/nbs/takwimu/cpi/CPI_{M.capitalize()}_{y}_Eng.pdf',
    'Rwanda': f'https://www.statistics.gov.rw/publication/consumer-price-index-cpi-{M}-{y}',
    'Ethiopia': 'https://www.statsethiopia.gov.et/our-survey-reports/',
    'Zambia': 'https://www.zamstats.gov.zm/index.php/publications/category/51-2021/',
    'Zimbabwe': 'https://www.zimstat.co.zw/cpi/',
    'Namibia': 'https://nsa.org.na/page/publications/',
    'Malawi': 'http://www.nsomalawi.mw/index.php?option=com_content&view=article&id=3&Itemid=39',
    'Mali': 'https://www.instat-mali.org/fr/publications/indice-harmonise-des-prix-a-la-consommation-ihpc',
    'Niger': 'https://www.stat-niger.org/?page_id=1558',
    'Mauritania': 'http://ansade.mr/index.php/19-indicateurs/21-indice-national-des-prix-a-consommation-inpc',
    'Mauritius': 'https://statsmauritius.govmu.org/Pages/Statistics/Monthly/Monthly-CPI.aspx',
    'Senegal': f'https://www.ansd.sn/index.php?option=com_ansd&view=titrepublication&id=6',
    'Sierra_Leone': 'http://www.statistics.sl/index.php/cpi.html',
    'Seychelles': f'https://www.nbs.gov.sc/downloads/economic-statistics/consumer-price-index/{y}',
    'Togo': 'https://inseed.tg/inflation-prix/'
    }
And = {
    'Benin': f'doc,ihpc,{y},{mf}',
    'Botswana': f'pdf,{m},{y}',
    'Burkina_Faso': f'pdf,{mf},{y},ihpc',
    'Burundi': f'pdf,{mf},{y},ipc',
    'Cote_dIvoire': '',
    'Gambia': f'consumer-price-index,{m},{y}',
    'Guinee': f'pdf,ihpc,{y},{mf}',
    'Kenya': f'{m},{y}',
    'Uganda': f'pdf,cpi,{m},{y}',
    'South_Africa': f'pdf,{m},{y}',
    'Ghana': f'pdf,{m},{y}',
    'Tanzania': '',
    'Rwanda': 'English',
    'Ethiopia': f'pdf,cpi,{m},{y}',
    'Zambia': f'{y},{m},monthly',
    'Zimbabwe': f'{y},_{Mn},cpi,pdf',
    'Namibia': f'cpi,{y},{m}',
    'Niger': f'doc,ihpcb2014,{y},{mf}',
    'Malawi':f'monthly,pdf,{y},{m}',
    'Mali': f'ihpc,{yn},{Mn}',
    'Mauritania': f'inpc,{y},{mf}',
    'Mauritius': f'cpi,{y},{m}',
    'Senegal': f'pdf,{mf},{y}',          #Mn or mf
    'Sierra_Leone': f'cpi,{y},{m}',
    'Seychelles': f'cpi,{y},{m}',
    'Togo': f'inhpc,{y},{mf}'
    }

Or = {
    'Benin': '',
    'Burkina_Faso': '',
    'Burundi': '',
    'Cote_dIvoire': '',
    'Gambia': '',
    'Guinee': '',
    'Kenya': 'cpi,consumer',
    'Uganda': 'publication',
    'South_Africa': f'P0141{M.capitalize()}{y}',
    'Ghana': '',
    'Botswana': 'Consumer_Price_Index,cpi,CPI',
    'Tanzania': '',
    'Rwanda': '',
    'Ethiopia': '',
    'Zambia': '',
    'Zimbabwe': '',
    'Namibia': '',
    'Niger': '',
    'Mali': '',
    'Malawi': '',
    'Mauritania': '',
    'Mauritius': '',
    'Senegal': '',
    'Sierra_Leone': '',
    'Seychelles': '',
    'Togo': '',
    }
Pages = {
    'Benin': '2',
    'Burkina_Faso': '4',
    'Burundi': '5',
    'Cote_dIvoire': '1',
    'Gambia': '2',
    'Guinee': '1',
    'Kenya': '1',
    'Uganda': '16',
    'South_Africa': '6',
    'Ghana': '8',
    'Botswana': [6,7],
    'Tanzania': '',
    'Rwanda': '3',
    'Ethiopia': '23',
    'Zambia': '5',
    'Zimbabwe': '1',
    'Namibia': '5',
    'Niger': '1',
    'Mali': '1',
    'Malawi': '1',
    'Mauritania': '1',
    'Mauritius': '2',
    'Senegal': '3',
    'Sierra_Leone': '6',
    'Seychelles': '16',
    'Togo': '',
    }
h = ['Food & non-alcoholic beverages', 'Alcoholic beverages, tobacco and narcotics', 'Clothing & footwear',
     'Housing, water, electricity, gas and other fuels',
     'Furnishings, household equipment and routine household maintenance', 'Health', 'Transport', 'Communication',
     'Recreation & culture', 'Education', 'Restaurants and hotels', 'Miscellaneous goods and services', 'All items']
code = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', '13']
indicator = 13*['Consumer price index']


h14 = ['Food & non-alcoholic beverages', 'Alcoholic beverages, tobacco and narcotics', 'Clothing & footwear',
     'Housing, water, electricity, gas and other fuels',
     'Furnishings, household equipment and routine household maintenance', 'Health', 'Transport', 'Communication',
     'Recreation & culture', 'Education', 'Restaurants and hotels', 'Insurance and Financial Services', 'Miscellaneous goods and services', 'All items']
code14 = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', '13', '14']
indicator14 = 14*['Consumer price index']


# in the dataframe.
def getIndexes(dfObj, value):
    # Empty list
    listOfPos = []

    # isin() method will return a dataframe with
    # boolean values, True at the positions
    # where element exists
    result = dfObj.isin([value])

    # any() method will return
    # a boolean series
    seriesObj = result.any()

    # Get list of column names where
    # element exists
    columnNames = list(seriesObj[seriesObj == True].index)

    # Iterate over the list of columns and
    # extract the row index where element exists
    for col in columnNames:
        rows = list(result[col][result[col] == True].index)

        for row in rows:
            listOfPos.append((row, col))

    # This list contains a list tuples with
    # the index of element in the dataframe
    return listOfPos
def render_to_pdf(obj):
    name = obj.name
    urlo = obj.url
    site = sites[name]
    check_and = And[name].split(',')
    check_or = Or[name].split(',')
    ext = 'pdf'
    country_folder = os.path.join(MEDIA_ROOT, 'Data', name)
    my_file = f'{name}_{m.capitalize()}_{y}.{ext}'
    full_path = os.path.join(country_folder, my_file)
    print(full_path)
    if name == 'Gambia':
        ext = 'xlsx'
        my_file = f'{name}_{m.capitalize()}_{y}.{ext}'
        full_path = os.path.join(country_folder, my_file)
    elif name == 'Niger' or name=='Benin':
        ext = 'docx'
        my_file = f'{name}_{m.capitalize()}_{y}.{ext}'
        full_path = os.path.join(country_folder, my_file)
    
    
    if not os.path.exists(country_folder):
        os.makedirs(country_folder)
    
    if os.path.isfile(full_path):
        return None
        '''
        elif name == 'Senegal':
            url = site
            # parsed_href = urlparse(url)
            # remove URL GET parameters, URL fragments, etc.
            # href = parsed_href.scheme + "://" + parsed_href.netloc + parsed_href.path
            print(url)
            pdf_response = requests.get(url)
            print(pdf_response.raise_for_status)
            msg = "Scrapping is a success!!!"
            return my_file, pdf_response, site, check_and, check_or, msg
        '''
    elif name == 'Cote_dIvoire':
        url = site
        pdf_response = requests.get(url)
        print(pdf_response.raise_for_status)
        msg = "Scrapping is a success!!!"
        return my_file, pdf_response, site, check_and, check_or, msg, full_path


    else:
        # target URL
        url = site

        if name == 'Malawi' and m in ['mar', 'jun', 'sep', 'dec']:
            check_and[0] = 'quartely'
        print(check_and)
        # make HTTP GET request to the target URL
        try:
            headers = requests.utils.default_headers()
            headers['User-Agent'] = '*'
            response = requests.get(url, headers=headers)
            content = BeautifulSoup(response.text, 'lxml')
            # extract URLs referencing PDF documents
            all_urls = content.find_all('a')
            # loop over all URLs in the Page
            for url in all_urls:
                # try URLs containing 'href' atribute
                try:
                    urll = url['href'].lower()
                    if name == 'Kenya':
                        doc_url = url['onclick']
                        urll = doc_url.lower()
                        if all(urll.find(check) > -1 for check in check_and):
                            # init Doc url
                            url_s = re.findall(r"'(.*?)'", doc_url, re.DOTALL)[0]
                            pdf_url = ''
                            # append base URL if no 'https' available in URL
                            if 'https:' not in url_s:
                                pdf_url = urlo + url_s

                            # otherwise use bare URL
                            else:
                                pdf_url = url_s
                            pdf_response = requests.get(pdf_url, headers=headers)
                            pdf_response.encoding = pdf_response.apparent_encoding
                            filename = unquote(pdf_response.url).split('/')[-1].replace(' ', '_')
                            print(pdf_response)
                            if any(filename.find(check) > -1 for check in check_or):
                                msg = "Scrapping is a success!!!"
                                return my_file, pdf_response, site, check_and, check_or,msg, full_path
                    elif name == 'Togo':
                        urlt = url.text.lower()
                        if all(urlt.find(check) > -1 for check in check_and):
                            pdf_url = ''
                            # append base URL if no 'https' available in URL
                            if 'http' not in url['href']:
                                pdf_url = urlo + url['href']
                            # otherwise use bare URL
                            else:
                                pdf_url = url['href']
                            # make HTTP GET request to fetch PDF bytes
                            pdf_response = requests.get(pdf_url, headers=headers)

                            msg = "Scrapping is a success!!!"
                            return my_file, pdf_response, site, check_and, check_or, msg, full_path

                    elif check_and == [] or all(urll.find(check) > -1 for check in check_and) or\
                            check_and[0] in url.text:
                        # init PDF url
                        pdf_url = ''
                        print(url['href'])
                        # append base URL if no 'https' available in URL
                        if 'http' not in url['href']:
                            pdf_url = urlo + url['href']
                        else:
                            pdf_url = url['href']
                        print(pdf_url)
                        # make HTTP GET request to fetch PDF bytes
                        # time.sleep(10)
                        pdf_response = requests.get(pdf_url, headers=headers)
                        print(pdf_response.status_code)
                        if pdf_response.status_code != requests.codes.ok:
                            print(" Not found")
                        # extract PDF file name
                        
                        filename = unquote(pdf_response.url).split('/')[-1].replace(' ','_')
                        if name == 'Uganda':
                            filename = filename.lower()
                            if 'publication' in filename.lower():
                                # write PDF to local file
                                msg = "Scrapping is a success!!!"
                                return my_file, pdf_response, site, check_and, check_or, msg
                        else:
                            if check_or == [] or any(urll.find(check) > -1 for check in check_or) or \
                                any(filename.find(check) > -1 for check in check_or):
                                msg ="Scrapping is a success!!!"
                                return my_file, pdf_response, site, check_and, check_or, msg, full_path
                # Skip all other URLs
                except Exception as e:
                    print("Error", e)
        except requests.exceptions.HTTPError as err:
            print('HTTP ERROR %s occured' % err)


def scrape_pdf(obj):
    name = obj.name
    page = Pages[name]
    my_file = f'{name}_{m.capitalize()}_{y}.pdf'
    my_excel = f'{name}_{m.capitalize()}_{y}.xlsx'
    country_folder = os.path.join(MEDIA_ROOT, 'Data', name)
    pdf_full_path = os.path.join(country_folder, my_file)
    excel_full_path = os.path.join(country_folder, my_excel)
    if os.path.isfile(excel_full_path):
        return None
    else:
        if os.path.isfile(pdf_full_path):
            if name == 'Botswana':
                with pp.open(pdf_full_path) as pdf:
                    # Get the first page of the object
                    page1 = pdf.pages[page[0]]
                    page2 = pdf.pages[page[1]]

                    table1 = page1.extract_tables()
                    table2 = page2.extract_tables()

                tb1 = pd.DataFrame(table1[0])
                tb1.columns = tb1.loc[1]
                tb1 = tb1.loc[2:].reset_index(drop=True)
                tb1 = tb1.replace('\n', ' ', regex=True)
                tb1.columns = tb1.columns.str.replace('\n', ' ', regex=True)

                tb2 = pd.DataFrame(table2[0])
                tb2.columns = tb2.loc[1:2].fillna('').apply(' '.join).str.strip()
                tb2 = tb2.loc[3:].reset_index(drop=True)
                tb2 = tb2.replace('\n', ' ', regex=True)
                tb2.columns = tb2.columns.str.replace('\n', ' ', regex=True)
                tb2.drop(tb2.columns[0], axis=1, inplace=True)

                tb = tb1.join(tb2)
                tb.columns.values[1] = 'Month'

                for i in range(len(tb.iloc[:, 0])):
                    if tb.iloc[i, 0] == '':
                        tb.iloc[i, 0] = tb.iloc[i - 1, 0]

                tb.iloc[:, 0] = tb.iloc[:, 0].astype(str) + '-' + tb.iloc[:, 1].astype(str)
                tb.drop(tb.columns[1], axis=1, inplace=True)
                nan_value = float("NaN")
                tb.replace("", nan_value, inplace=True)
                tb = tb.dropna(thresh=len(tb.columns) - 5)
                tb = tb.reset_index(drop=True)
                tbr = tb.iloc[1:-1, :14]
                tbr = tbr.T
                tbr.columns = tbr.iloc[0]
                tb = tbr[1:]
                tb.reset_index(level=0, inplace=True)
                tb = tb.iloc[:, 1:]
                tb.insert(0, 'COICOP label', h)
                tb.insert(0, 'COICOP CODE', code)
                tb.insert(0, 'Indicator', indicator)
                tb.insert(0, 'Country', 13 * [name])
                tb.iloc[:, 4:] = tb.iloc[:, 4:].astype('float')
                return my_excel, my_file, tb

            elif name == 'Ethiopia':
                table = camelot.read_pdf(pdf_full_path, multiple_tables=True, pages='23', line_scale=40, encoding='utf-8')
                tb1 = pd.DataFrame(table[0].df)
                tb1 = tb1.loc[2:]
                tb1 = tb1.replace('\n', ' ', regex=True)
                tb1.drop(tb1.columns[0], axis=1, inplace=True)
                tb1.insert(0, 15, tb1.pop(15))
                tb1.insert(14, 1, tb1.pop(1))
                nan_value = float("NaN")
                tb1.replace("", nan_value, inplace=True)
                tb1 = tb1.dropna(thresh=len(tb1.columns) - 5)
                tb1 = tb1.reset_index(drop=True)
                tb1 = tb1.drop([1, 2, 3, 4])
                for i in range(len(tb1.iloc[:, 0]) - 1):
                    M = tb1.iloc[i + 1, 0].split(' ')
                    if M[-1] == "''":
                        mmm = tb1.iloc[i, 0].split('-')
                        tb1.iloc[i + 1, 0] = M[0] + '-' + mmm[-1]
                    else:
                        tb1.iloc[i + 1, 0] = M[0] + '-' + M[-1]
                tb1 = tb1.T
                tb1.reset_index(drop=True)
                tb1 = tb1.drop(3)
                tb1.columns = tb1.iloc[0]
                tb1 = tb1[1:]
                tb1.columns.values[0] = 'COICOP label'
                tb1.reset_index()
                tb1['COICOP label'] = h
                tb1.insert(0, 'COICOP CODE', code)
                tb1.insert(0, 'Indicator', indicator)
                tb1.insert(0, 'Country', 13 * ['Ethiopia'])
                tb1.iloc[:, 4:] = tb1.iloc[:, 4:].astype('float')

                return my_excel, my_file, tb1

            elif name == 'South_Africa':
                table = camelot.read_pdf(pdf_full_path, multiple_tables=True, pages='7-8', line_scale=120, encoding='utf-8')
                tb1 = pd.DataFrame(table[0].df)
                tb1 = tb1.replace('\n', ' ', regex=True)
                nan_value = float("NaN")
                tb1.replace("", nan_value, inplace=True)
                tb1 = tb1.dropna(subset=[0])
                tb2 = pd.DataFrame(table[1].df)
                tb2 = tb2.replace('\n', ' ', regex=True)
                nan_value = float("NaN")
                tb2.replace("", nan_value, inplace=True)
                tb2 = tb2.dropna(subset=[0])[1:]
                tb = tb1.append(tb2)
                tb = tb.dropna(axis=1)
                tb = tb.iloc[:, [0, 1,2,3]]
                tb = tb.replace(',', '.', regex=True)
                tb.iloc[1:, 1:4] = tb.iloc[1:, 1:4].astype(float)
                tb = tb.reset_index(drop=True)
                tb.loc[len(tb.index)] = tb.iloc[1, :]
                tb = tb.drop(tb.index[1])
                tb.columns = tb.iloc[0]
                tb = tb[1:]
                tb.columns.values[0] = 'COICOP label'
                tb.reset_index()
                tb['COICOP label'] = h
                tb.insert(0, 'COICOP CODE', code)
                tb.insert(0, 'Indicator', indicator)
                tb.insert(0, 'Country', 13 * ['South Africa'])

                return my_excel, my_file, tb

            elif name == 'Uganda':
                table = camelot.read_pdf(pdf_full_path, flavor='stream', pages='22', encoding='utf-8')
                df = pd.DataFrame(table[0].df)
                df = df.iloc[:, 7:]
                nan_value = float("NaN")
                df.replace("", nan_value, inplace=True)
                df = df.dropna()
                df = df.reset_index(drop=True)
                df.iloc[1:, :] = df.iloc[1:, :].astype(float)
                df.loc[len(df.index)] = df.iloc[1, :]
                df = df.drop(df.index[1])
                df = df.reset_index(drop=True)
                df.columns = df.iloc[0]
                df = df[1:]
                df.insert(0, 'COICOP label', h14)
                df.insert(0, 'COICOP CODE', code14)
                df.insert(0, 'Indicator', indicator14)
                df.insert(0, 'Country', 14 * [name])
                #df.insert(0, 'COICOP label', h)
                #df.insert(0, 'COICOP CODE', code)
                #df.insert(0, 'Indicator', indicator)
                #df.insert(0, 'Country', 13 * [name])

                return my_excel, my_file, df

            elif name == 'Rwanda':
                table = camelot.read_pdf(pdf_full_path, flavor='stream', pages='9', encoding='utf-8')
                df = pd.DataFrame(table[0].df)
                df = df.drop(df.index[5:10])
                df = df.reset_index(drop=True)
                df = df.iloc[2:, 3:6]
                df = df.reset_index(drop=True)
                nan_value = float("NaN")
                df.replace("", nan_value, inplace=True)
                df = df.dropna()
                df = df.reset_index(drop=True)
                df.iloc[1:, :] = df.iloc[1:, :].astype(float)
                df.loc[len(df.index)] = df.iloc[1, :]
                df = df.drop(df.index[1])
                df = df.reset_index(drop=True)
                df.columns = df.iloc[0]
                df = df[1:]
                df = df.reset_index(drop=True)
                df.insert(0, 'COICOP label', h)
                df.insert(0, 'COICOP CODE', code)
                df.insert(0, 'Indicator', indicator)
                df.insert(0, 'Country', 13 * [name])

                return my_excel, my_file, df

            elif name == 'Zimbabwe':
                pdf = PdfFileReader(open(pdf_full_path, 'rb'))
                p_num = pdf.getNumPages()
                if p_num > 3:
                    table = camelot.read_pdf(pdf_full_path, flavor='stream', pages='4', encoding='utf-8')
                    df = pd.DataFrame(table[0].df)
                    df = df.loc[15:]
                    df = df.replace(',', '', regex=True)
                    df = df.reset_index(drop=True)
                    for i in range(len(df.iloc[:, 0])):
                        col1 = df.iloc[i, 0].split(' ')
                        if len(col1) == 4:
                            df.iloc[i, 0] = col1[0] + ' - ' + col1[1]
                            df.iloc[i, 1] = col1[-1]
                        elif len(col1) == 1:
                            df.iloc[i, 0] = df.iloc[i - 1, 0].split(' ')[0] + " - " + col1[0]
                        else:
                            df.iloc[i, 0] = col1[0] + ' - ' + col1[1]
                    df = df.T
                    df.columns = df.iloc[0]
                    df = df[1:-2]
                    df.insert(0, 'COICOP label', h)
                    df.insert(0, 'COICOP CODE', code)
                    df.insert(0, 'Indicator', indicator)
                    df.insert(0, 'Country', 13 * [name])
                    df.iloc[:, 4:] = df.iloc[:, 4:].astype(float)

                    return my_excel, my_file, df
                else:
                    return None

            elif name == 'Burkina_Faso':
                table = camelot.read_pdf(pdf_full_path, pages='1', multiple_tables=True, encoding='utf-8')
                df = pd.DataFrame()
                for i in range(len(table)):
                    if table[i].shape[0] < 13 or table[i].shape[1] < 7:
                        continue
                    else:
                        df = pd.DataFrame(table[i].df)
                search = mf + '-' + f'{int(yn) - 1}'
                print(search)
                listOfPositions = getIndexes(df, search)
                if len(listOfPositions) == 0:
                    search = mf + '-' + f'{int(yn)}'
                    print(search)
                    listOfPositions = getIndexes(df, search)
                i = listOfPositions[0][0]
                j = listOfPositions[0][1]
                df = df.iloc[i:, j:j + 4]
                df.columns = df.iloc[0]
                df = df[1:]
                df = df.replace(',', '.', regex=True)
                df = df.reset_index(drop=True)
                df.loc[len(df.index)] = df.iloc[0, :]
                df = df.drop(df.index[0])
                df = df.reset_index(drop=True)
                df.insert(0, 'COICOP label', h)
                df.insert(0, 'COICOP CODE', code)
                df.insert(0, 'Indicator', indicator)
                df.insert(0, 'Country', 13 * ['Burkina Faso'])

                df.iloc[:, 4:] = df.iloc[:, 4:].astype(float)

                return my_excel, my_file, df

            elif name == "Burundi":
                table = camelot.read_pdf(pdf_full_path, pages='5,6', multiple_tables=True, line_scale=80, encoding='utf-8')
                df1 = pd.DataFrame(table[0].df)
                df2 = pd.DataFrame(table[1].df)
                df2 = df2[2:]
                df = df1.append(df2)
                df = df.reset_index(drop=True)
                df = df.replace('\n', ' ', regex=True)
                if df.iloc[1, 4] == '':
                    df.iloc[1, 4] = df.iloc[1, 5].split(' ')[0]
                df = df.loc[1:3].append(df.loc[17:27])
                df = df.iloc[:, [2, 3, 4]]
                df = df.replace(',', '.', regex=True)
                df.iloc[1:, :] = df.iloc[1:, :].astype(float)
                df = df.reset_index(drop=True)
                df.loc[len(df.index)] = df.iloc[1, :]
                df = df.drop(df.index[1])
                df.columns = df.iloc[0]
                df = df[1:]
                df = df.reset_index(drop=True)
                df.insert(0, 'COICOP label', h)
                df.insert(0, 'COICOP CODE', code)
                df.insert(0, 'Indicator', indicator)
                df.insert(0, 'Country', 13 * ['Burundi'])

                return my_excel, my_file, df

            elif name == 'Sierra_Leone':
                pdf = PdfFileReader(open(pdf_full_path, 'rb'))
                p_num = pdf.getNumPages()
                print(p_num)
                if p_num == 9:
                    table = camelot.read_pdf(pdf_full_path, pages='9', flavor='stream', multiple_tables=True, encoding='utf-8')
                    df = pd.DataFrame(table[0].df)
                else:
                    table = camelot.read_pdf(pdf_full_path, pages='9-10', flavor='stream', multiple_tables=True,encoding='utf-8')
                    df1 = pd.DataFrame(table[0].df)
                    df2 = pd.DataFrame(table[1].df)
                    df = df1.append(df2)
                df = df[1:]
                for i in range(len(df)):
                    if df.iloc[i, 1] == '':
                        df.iloc[i, 1:] = df.iloc[i + 1, 1:]
                nan_value = float("NaN")
                df.replace("", nan_value, inplace=True)
                df = df.dropna(how='any')
                df = df.T
                df.columns = df.iloc[0]
                df = df[1:]
                df = df.reset_index(drop=True)
                df.insert(0, 'COICOP label', h)
                df.insert(0, 'COICOP CODE', code)
                df.insert(0, 'Indicator', indicator)
                df.insert(0, 'Country', 13 * ['Sierra Leone'])
                df.iloc[:, 4:] = df.iloc[:, 4:].astype('float')

                return my_excel, my_file, df

            elif name == 'Senegal':
                #table = camelot.read_pdf(pdf_full_path, pages='3', line_scale=60, multiple_tables=True, encoding='utf-8')
                table = camelot.read_pdf(pdf_full_path, pages='3', flavor='stream', multiple_tables=True, encoding='utf-8')
                df = pd.DataFrame(table[0].df)
                nan_value = float("NaN")
                df.replace("", nan_value, inplace=True)
                df = df.loc[3:]
                df = df.dropna(thresh=len(df.columns) - 3)
                df = df.dropna(axis=1, thresh=len(df) - 4)
                df = df.reset_index(drop=True)
                df = df.iloc[:, 2:7]
                for i in range(len(df.columns)-1):
                    if df.iloc[0, i] == '':
                        col2 = df.iloc[0, i+1].split(' ')
                        df.iloc[0, i] = col2[0]
                        df.iloc[0, i + 1] = col2[-1]
                df.loc[len(df.index)] = df.iloc[1, :]
                df = df.drop(df.index[1])
                df.columns = df.iloc[0]
                df = df.replace(',', '.', regex=True)
                df = df[1:]
                df.insert(0, 'COICOP label', h)
                df.insert(0, 'COICOP CODE', code)
                df.insert(0, 'Indicator', indicator)
                df.insert(0, 'Country', 13 * ['Senegal'])
                df.iloc[:, 4:] = df.iloc[:, 4:].astype(float)

                return my_excel, my_file, df

            elif name == 'Togo':
                table = camelot.read_pdf(pdf_full_path, pages='1', flavor='stream', multiple_tables=True, encoding='utf-8')
                df = pd.DataFrame()
                for i in range(len(table)):
                    if table[i].shape[0] < 25 or table[i].shape[1] < 7:
                        continue
                    else:
                        df = pd.DataFrame(table[i].df)
                        break
                search = mf + '-' + f'{int(yn) - 1}'
                listOfPositions = getIndexes(df, search)
                if len(listOfPositions) == 0:
                    search = mf + '-' + f'{int(yn)}'
                    listOfPositions = getIndexes(df, search)
                i = listOfPositions[0][0]
                df = df.iloc[i:, 2:7]
                df = df.reset_index(drop=True)
                rr = []
                for r in df.iloc[0, :].values:
                    rr.extend(r.split())
                df.columns = rr
                df = df[1:]
                nan_value = float("NaN")
                df.replace("", nan_value, inplace=True)
                df = df.dropna(thresh=2)
                df = df.reset_index(drop=True)
                df = df.iloc[:2,:].append(df.iloc[10:,:])
                df = df.reset_index(drop=True)
                df.loc[len(df.index)] = df.iloc[0, :]
                df = df.drop(df.index[0])
                df = df.reset_index(drop=True)
                df = df.replace(',', '.', regex=True)
                df.insert(0, 'COICOP label', h)
                df.insert(0, 'COICOP CODE', code)
                df.insert(0, 'Indicator', indicator)
                df.insert(0, 'Country', 13 * [name])
                df.iloc[:, 4:] = df.iloc[:, 4:].astype(float)

                return my_excel, my_file, df

            elif name == 'Cote_dIvoire':
                table = camelot.read_pdf(pdf_full_path, pages='1', flavor='stream', multiple_tables=True, encoding='utf-8')
                df1 = pd.DataFrame()
                for i in range(len(table)):
                    if table[i].shape[0] < 25 or table[i].shape[1] <7:
                        continue
                    else:
                        df1 = pd.DataFrame(table[i].df)
                search = mf+'-'+f'{int(yn)-1}'
                print(search)
                listOfPositions = getIndexes(df1, search)
                if len(listOfPositions) == 0:
                    search = mf + '-' + f'{int(yn)}'
                    print(search)
                    listOfPositions = getIndexes(df1, search)
                i = listOfPositions[0][0]
                df1 = df1.iloc[i:, 2:7]
                df1 = df1.reset_index(drop=True)
                rr = []
                for r in df1.iloc[0, :].values:
                    rr.extend(r.split())
                df1.columns = rr
                df1 = df1[1:]
                nan_value = float("NaN")
                df1.replace("", nan_value, inplace=True)
                df1 = df1.dropna(thresh=1)
                df1 = df1.reset_index(drop=True)
                df = df1.iloc[0:2, :].append(df1.iloc[10:, :])
                df = df.reset_index(drop=True)
                df.loc[len(df.index)] = df.iloc[0, :]
                df = df.drop(df.index[0])
                df = df.reset_index(drop=True)
                df = df.replace(',', '.', regex=True)
                df.insert(0, 'COICOP label', h)
                df.insert(0, 'COICOP CODE', code)
                df.insert(0, 'Indicator', indicator)
                df.insert(0, 'Country', 13 * ['Côte dIvoire'])
                df.iloc[:, 4:] = df.iloc[:, 4:].astype(float)

                return my_excel, my_file, df

            elif name == 'Mauritania':
                table = camelot.read_pdf(pdf_full_path, pages='1', flavor='stream', row_tol=4,column_tol=4,multiple_tables=True, encoding='utf-8')
                df1 = pd.DataFrame()
                for i in range(len(table)):
                    if table[i].shape[0] < 25 or table[i].shape[1] < 7:
                        continue
                    else:
                        df1 = pd.DataFrame(table[i].df)
                search = mf + '-' + f'{int(yn) - 1}'
                print(search)
                listOfPositions = getIndexes(df1, search)
                if len(listOfPositions) == 0:
                    search = mf + '-' + f'{int(yn)}'
                    print(search)
                    listOfPositions = getIndexes(df1, search)
                i = listOfPositions[0][0]
                df1 = df1.iloc[i:, 2:6]
                df1 = df1.reset_index(drop=True)
                rr = []
                for r in df1.iloc[0, :].values:
                    rr.extend(r.split())
                df1.columns = rr
                df1 = df1[1:]
                nan_value = float("NaN")
                df1.replace("", nan_value, inplace=True)
                df1 = df1.dropna(thresh=1)
                df1 = df1.reset_index(drop=True)
                df = df1.iloc[0:1, :].append(df1.iloc[10:, :])
                df = df.reset_index(drop=True)
                df = df[:13]
                df = df.replace(',', '.', regex=True)
                df.insert(0, 'COICOP label', h)
                df.insert(0, 'COICOP CODE', code)
                df.insert(0, 'Indicator', indicator)
                df.insert(0, 'Country', 13 * ['Mauritanie'])
                df.iloc[:, 4:] = df.iloc[:, 4:].astype(float)

                return my_excel, my_file, df

            elif name == 'Mauritius':
                table = camelot.read_pdf(pdf_full_path, pages='2', line_scale=40, multiple_tables=True, encoding='utf-8')
                df1 = pd.DataFrame()
                for i in range(len(table)):
                    if table[i].shape[0] < 10 or table[i].shape[1] < 3:
                        continue
                    else:
                        df1 = pd.DataFrame(table[i].df)
                df = df1.iloc[:14, 1:3]
                df = df.replace('\n', ' ', regex=True)
                nan_value = float("NaN")
                df.replace("", nan_value, inplace=True)
                df = df.dropna()
                df = df.reset_index(drop=True)
                df.columns = df.iloc[0]
                df = df[1:]
                df = df.replace(',', '.', regex=True)
                df.insert(0, 'COICOP label', h)
                df.insert(0, 'COICOP CODE', code)
                df.insert(0, 'Indicator', indicator)
                df.insert(0, 'Country', 13 * ['Mauritanie'])
                df.iloc[:, 4:] = df.iloc[:, 4:].astype(float)

                return my_excel, my_file, df

            elif name == 'Mali':
                table = camelot.read_pdf(pdf_full_path, pages='1', flavor='stream', multiple_tables=True, encoding='utf-8')
                df = pd.DataFrame()
                for i in range(len(table)):
                    if table[i].shape[0] < 25 or table[i].shape[1] < 7:
                        continue
                    else:
                        df = pd.DataFrame(table[i].df)
                        break
                search = mf+'.-'+f'{int(yn)-1}'
                print(search)
                listOfPositions = getIndexes(df, search)
                if len(listOfPositions) == 0:
                    search = mf+'.-'+f'{yn}'
                    print(search)
                    listOfPositions = getIndexes(df, search)
                i = listOfPositions[0][0]
                j = listOfPositions[0][1]
                df = df.iloc[i:, j:j + 5]
                df = df.reset_index(drop=True)
                rr = []
                for r in df.iloc[0, :].values:
                    rr.extend(r.split())
                df.columns = rr

                df = df[1:]
                nan_value = float("NaN")
                df.replace("", nan_value, inplace=True)
                df = df.dropna(thresh=1)
                df = df.reset_index(drop=True)
                df1 = df.iloc[0:2, :].append(df.iloc[9:11, :]).append(df.iloc[12:13, :]).append(df.iloc[14:17, :]).append(df.iloc[18:, :])
                df = df1.reset_index(drop=True)
                df.loc[len(df.index)] = df.iloc[0, :]
                df = df.drop(df.index[0])
                df = df.reset_index(drop=True)
                df = df.replace(',', '.', regex=True)
                df.insert(0, 'COICOP label', h)
                df.insert(0, 'COICOP CODE', code)
                df.insert(0, 'Indicator', indicator)
                df.insert(0, 'Country', 13 * ['Mali'])
                df.iloc[:, 4:] = df.iloc[:, 4:].astype(float)

                return my_excel, my_file, df

            elif name == 'Ghana':
                table = camelot.read_pdf(pdf_full_path, pages='5,7,8', flavor='stream', multiple_tables=True, encoding='utf-8')
                df1 = pd.DataFrame(table[0].df)
                df1 = df1.iloc[2:, :2]
                df1 = df1.T
                df2 = pd.DataFrame(table[2].df)
                df2 = df2.iloc[3:4, 2:3]
                df3 = pd.DataFrame(table[1].df)
                df3 = df3.iloc[3:-1, 2:3]
                df4 = df2.append(df3)
                df4 = df4.reset_index(drop=True)
                df = df4.append(df1)
                df = df.reset_index(drop=True)
                df.columns = df.iloc[13]
                df = df.drop(df.index[13])
                df = df.reset_index(drop=True)
                df.iloc[:-1, -1] = df.iloc[:-1, 0]
                df.iloc[:-1, 0] = np.nan

                df.insert(0, 'COICOP label', h14)
                df.insert(0, 'COICOP CODE', code14)
                df.insert(0, 'Indicator', indicator14)
                df.insert(0, 'Country', 14 * ['Ghana'])
                df.iloc[:, 4:] = df.iloc[:, 4:].astype(float)
                return my_excel, my_file, df

            elif name == 'Malawi':
                search = 'National consumer price index'
                if m in ['mar', 'jun', 'sep', 'dec']:
                    page = '9'
                    search = 'National Consumer Price Index'
                table = camelot.read_pdf(pdf_full_path, pages=page, flavor='stream',  multiple_tables=True, encoding='utf-8')

                df = pd.DataFrame(table[0].df)
                nan_value = float("NaN")
                df.replace("", nan_value, inplace=True)
                df = df.dropna(thresh=5, axis=1)

                print(search)
                listOfPositions = getIndexes(df, search)
                i = listOfPositions[0][0]

                df = df.iloc[i + 1:i + 14, -3:]
                df = df.reset_index(drop=True)
                if 'jan' == m:
                    df.columns = [months[-1].capitalize() + '-' + str(y - 1), months[-2].capitalize() + '-' + yn,
                                  months[-1].capitalize() + '-' + str(y - 2)]
                elif 'feb' == m:
                    df.columns = [months[months.index(m) - 1].capitalize() + '-' + str(y),
                                  months[months.index(m) - 2].capitalize() + '-' + str(y - 1),
                                  months[months.index(m) - 1].capitalize() + '-' + str(y - 1)]
                else:
                    df.columns = [months[months.index(m) - 1].capitalize() + '-' + str(y),
                                  months[months.index(m) - 2].capitalize() + '-' + yn,
                                  months[months.index(m) - 1].capitalize() + '-' + str(y - 1)]
                df.loc[len(df.index)] = df.iloc[0, :]
                df = df.drop(df.index[0])
                df = df.reset_index(drop=True)
                df.iloc[-1,-1] = df.iloc[-1,-1].replace('..','.')

                df.insert(0, 'COICOP label', h)
                df.insert(0, 'COICOP CODE', code)
                df.insert(0, 'Indicator', indicator)
                df.insert(0, 'Country', 13 * [name])
                print(df)
                df.iloc[:, 4:] = df.iloc[:, 4:].astype(float)

                return my_excel, my_file, df

            elif name == 'Seychelles':
                table = camelot.read_pdf(pdf_full_path, multiple_tables=True, flavor='stream', pages='7', encoding='utf-8')
                df = pd.DataFrame(table[0].df)
                df = df.replace('\n', ' ', regex=True)
                df = df[:-2]
                df.iloc[2:, 2:] = df.iloc[2:, 2:].astype(float)
                n = len(df.columns)
                weight1 = []
                for i in range(n - 2):
                    row2 = df.iloc[0, i + 2].split(' ')
                    weight1.append(float(row2[-1]))
                w1 = np.array(weight1)
                w2 = np.array(df.iloc[26, [2, 3, 15, 16]], dtype=float)
                w1Food = w1[:2]
                w1Alchohol = w1[13:15]
                w2Food = w2[:2]
                w2Alchohol = w2[-2:]

                w1Fave = w1Food / (sum(w1Food))
                w1Aave = w1Alchohol / (sum(w1Alchohol))
                w2Fave = w2Food / (sum(w2Food))
                w2Aave = w2Alchohol / (sum(w2Alchohol))

                food1 = df.iloc[2:26, 2] * w1Fave[0] + df.iloc[2:26, 3] * w1Fave[1]
                food2 = df.iloc[27:, 2] * w2Fave[0] + df.iloc[27:, 3] * w2Fave[1]

                F1 = food1.values.tolist()
                F1.insert(0, sum(w1Food))
                F2 = food2.values.tolist()
                F2.insert(0, sum(w2Food))
                F1.extend(F2)
                alchohol1 = df.iloc[2:26, 15] * w1Aave[0] + df.iloc[2:26, 3] * w1Aave[1]
                alchohol2 = df.iloc[27:, 15] * w2Aave[0] + df.iloc[27:, 16] * w2Aave[1]
                A1 = alchohol1.values.tolist()
                A1.insert(0, sum(w1Alchohol))
                A2 = alchohol2.values.tolist()
                A2.insert(0, sum(w2Alchohol))
                A1.extend(A2)

                df = df.reset_index(drop=True)
                df.iloc[:, 0] = df.iloc[:, 0].astype(str) + '-' + df.iloc[:, 1].astype(str)
                df.drop(df.columns[1], axis=1, inplace=True)

                for i in range(len(df)):
                    if df.iloc[i, 0][0] == '-':
                        ys = df.iloc[i - 1, 0].split('-')[0]
                        df.iloc[i, 0] = ys + df.iloc[i, 0]
                df.iloc[1, 1:] = weight1
                df.iloc[1, 0] = 'Weights(1)-'
                col1 = df.iloc[:, 0]
                df = df.iloc[:, 16:]
                df.insert(0, 'Year-Month', col1)
                df = df[1:]
                df = df.reset_index(drop=True)
                df.insert(1, 'Alchool', A1)
                df.insert(1, 'Food', F1)
                df = df.T
                df.columns = df.iloc[0]
                df = df[1:]
                df = df.reset_index(drop=True)
                df.insert(0, 'COICOP label', h)
                df.insert(0, 'COICOP CODE', code)
                df.insert(0, 'Indicator', indicator)
                df.insert(0, 'Country', 13 * ['Seychelles'])
                df.iloc[:, 4:] = df.iloc[:, 4:].astype(float)
                return my_excel, my_file, df

            elif name == 'Guinee':
                table = camelot.read_pdf(pdf_full_path, pages='1', line_scale=30, multiple_tables=True,  encoding='utf-8')
                df1 = pd.DataFrame()
                for i in range(len(table)):
                    if table[i].shape[0] < 5 or table[i].shape[1] < 5:
                        continue
                    else:
                        df1 = pd.DataFrame(table[i].df)
                search = mf + '.-' + f'{int(yn) - 1}'
                listOfPositions = getIndexes(df1, search)
                if len(listOfPositions) == 0:
                    search = ''
                    print(search)
                    listOfPositions = getIndexes(df1, search)
                i = listOfPositions[0][0]
                df1 = df1.iloc[i:, 3:8]
                df1 = df1.reset_index(drop=True)
                df1 = df1.replace('\n', ' ', regex=True)
                df1 = df1.replace(',', '.', regex=True)
                for i in range(1, len(df1)):
                    rr = []
                    for r in df1.iloc[i, :].values:
                        if r != '':
                            rr.extend(r.split())
                    df1.iloc[i, :] = rr[:]

                df1.columns = df1.iloc[0]
                df1 = df1[1:]

                df1 = df1.reset_index(drop=True)
                df1.loc[len(df1.index)] = df1.iloc[0, :]
                df1 = df1.drop(df1.index[0])
                nan_value = float("NaN")
                df1.replace("", nan_value, inplace=True)
                df1 = df1.dropna(thresh=1)
                df1 = df1.reset_index(drop=True)

                df = df1.iloc[0:1, :].append(df1.iloc[8:, :])
                df = df.reset_index(drop=True)

                df = df.T
                df.insert(1, '', 5 * np.nan)
                df.insert(7, 'co', 5 * np.nan)
                df = df.T
                df = df.reset_index(drop=True)
                df.insert(0, 'COICOP label', h)
                df.insert(0, 'COICOP CODE', code)
                df.insert(0, 'Indicator', indicator)
                df.insert(0, 'Country', 13 * [name])
                df.iloc[:, 4:] = df.iloc[:, 4:].astype(float)

                return my_excel, my_file, df

            elif name == 'Niger':
                table = camelot.read_pdf(pdf_full_path, pages='1',line_scale=60, multiple_tables=True, encoding='utf-8')
                df = pd.DataFrame()
                for i in range(len(table)):
                    if table[i].shape[0] < 13 or table[i].shape[1] <5:
                        continue
                    else:
                        df = pd.DataFrame(table[i].df)
                        break
                df = df.replace('\n', ' ', regex=True)
                df = df.replace(',', '.', regex=True)
                nan_value = float("NaN")
                df.replace("", nan_value, inplace=True)
                df = df.dropna(thresh=5)
                #search = mf+'-'+f'{int(yn)-1}'
                search = mf.capitalize() + ' ' + f'{int(y) - 1}'
                print(search)
                listOfPositions = getIndexes(df, search)
                if len(listOfPositions) == 0:
                    search = ''
                    listOfPositions = getIndexes(df, search)
                i = listOfPositions[0][0]
                j = listOfPositions[0][1]
                df = df.iloc[i:, j:j+5]
                df = df.reset_index(drop=True)
                df.columns = df.iloc[0,:]
                df = df.drop(df.index[0])
                df = df.reset_index(drop=True)
                df.loc[len(df.index)] = df.iloc[0,:]
                df = df.drop(df.index[0])
                df = df.reset_index(drop=True)
                df.insert(0, 'COICOP label', h)
                df.insert(0, 'COICOP CODE', code)
                df.insert(0, 'Indicator', indicator)
                df.insert(0, 'Country', 13 * [name])
                df.iloc[:, 4:] = df.iloc[:, 4:].astype(float)

                return my_excel, my_file, df
            '''
            elif name == 'Namibia':
                table = camelot.read_pdf(pdf_full_path, pages='22-26',line_scale=20, multiple_tables=True, encoding='utf-8')
                df = pd.DataFrame()
                for i in range(len(table)):
                    df = df.append(table[i].df)
                df = df.reset_index(drop=True)
                nan_value = float("NaN")
                df.replace("", nan_value, inplace=True)
                dt1 = df.iloc[2,7:10]
                dt1=dt1.reset_index(drop=True)
                dt2 = df.loc[90]
                for i in range( len(dt1)):
                    H = dt1[i].split('  ')
                    if len(H)>1:
                        dt1[i]= H[0]
                df = df.dropna( subset=[0])
                if len(df)<=12:
                    df = df.append(dt2[1:])
                df = df.iloc[:,7:10]
                df.columns = dt1
                df.reset_index(drop=True)
                df.loc[len(df.index)] = df.iloc[0, :]
                df = df.drop(df.index[0])
                df = df.reset_index(drop=True)
                df.insert(0, 'COICOP label', h)
                df.insert(0, 'COICOP CODE', code)
                df.insert(0, 'Indicator', indicator)
                df.insert(0, 'Country', 13 * ['Namibia'])

                return my_excel, my_file, df
            '''


        else:
            #msg = 'Data not found'
            return None

def report(obj):
    return None


'''    
    name = obj.name
    pdf_file = f'{name}_{m.capitalize()}_{y}.pdf'
    prev_file = f'{name}_{p_m.capitalize()}_{y}.xlsx'
    prev_sh = f'{name}_{p_m.capitalize()}_{y}'
    
    cur_file = f'{name}_{m.capitalize()}_{y}.xlsx'
    cur_sh = f'{name}_{m.capitalize()}_{y}'
    report_file = f'Report_{name}_{m.capitalize()}_{y}.xlsx'
    country_folder = os.path.join(MEDIA_ROOT, 'Data', name)
    prev_full_path = os.path.join(country_folder, prev_file)
    cur_full_path = os.path.join(country_folder, cur_file)
    report_full_path = os.path.join(country_folder, report_file)
    
    print(report_full_path)
    if os.path.isfile(report_full_path):
        return None
    else:
        if os.path.isfile(cur_full_path):
            prev_df = pd.read_excel(prev_full_path, sheet_name=prev_sh)
            cur_df = pd.read_excel(cur_full_path, sheet_name=cur_sh)
            if name == 'Botswana':
                if m == 'feb':
                    p = prev_df.iloc[-3, 2:15]
                    c = cur_df.iloc[-3, 2:15]
                else:
                    p = prev_df.iloc[-2, 2:15]
                    c = cur_df.iloc[-3, 2:15]
            elif name == 'Ethiopia':
                p = prev_df.iloc[-1, 1:]
                c = cur_df.iloc[-2, 1:]
            r = c.copy()

            for i in range(len(p)):

                if pd.isnull(p[i]) and not pd.isnull(c[i]):
                    r[i] = 'New'
                elif pd.isnull(c[i]) and not pd.isnull(p[i]):
                    r[i] = 'Removed'
                elif not pd.isnull(p[i]) and not pd.isnull(c[i]) and float(p[i])!=float(c[i]):
                    change = ((float(p[i])-float(c[i]))/float((p[i])))*100
                    print(type(change))
                    r[i] = '%0.2f'%(change) +' %'
                else:
                    r[i] = None
                
            
            #R = c.compare(r, keep_shape=True)
            if name == 'Botswana':
                inx = prev_df.columns[2:15]
            elif name == 'Ethiopia':
                inx = prev_df.columns[1:15]
            R = pd.concat([c,r], axis=1, join="inner")
            R.columns = ['Value', 'Changes']
            R.index = inx
            R.index.name = 'COICOP label'
            
            return R, pdf_file, report_file
        else:
            return None
'''
        


        
        

        


        
    

