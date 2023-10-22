from django.db import models
from django.shortcuts import reverse
import os

Countries = (('Benin', 'Benin'),
    ('Botswana', 'Botswana'),
    ('Burkina_Faso', 'Burkina_Faso'),
    ('Burundi', 'Burundi'),
    ('Cote_dIvoire', 'Cote_dIvoire'),
    ('Ethiopia', 'Ethiopia'),
    ('Gambia', 'Gambia'),
    ('Ghana', 'Ghana'),
    ('Guinee', 'Guinee'),
    ("Kenya", "Kenya"),
    ("Namibia", "Namibia"),
    ('Niger', 'Niger'),
    ('Malawi', 'Malawi'),
    ('Mali', 'Mali'),
    ('Mauritania', 'Mauritania'),
    ('Mauritius', 'Mauritius'),
    ('Rwanda', 'Rwanda'),
    ('Senegal', 'Senegal'),
    ('Seychelles', 'Seychelles'),
    ('Sierra_Leone', 'Sierra_Leone'),
    ('South_Africa', 'South_Africa'),
    ('Tanzania', 'Tanzania'),
    ('Togo', 'Togo'),
    ("Uganda", "Uganda"),
    ('Zambia', 'Zambia'),
    ('Zimbabwe', 'Zimbabwe')
)

URLs = {
    'Benin': 'https://insae.bj',
    'Botswana': 'https://www.statsbots.org.bw',
    'Burkina_Faso': 'http://www.insd.bf',
        'Burundi': 'https://www.isteebu.bi',
        'Cote_dIvoire': 'http://www.ins.ci/',
        'Ethiopia': 'https://www.statsethiopia.gov.et/',
        'Gambia': 'https://www.gbosdata.org',
        'Ghana': 'https://www.statsghana.gov.gh/',
        'Guinee': 'https://www.stat-guinee.org',
        'Kenya': 'https://www.knbs.or.ke',
        'Namibia': 'https://nsa.org.na',
        'Niger': 'https://www.stat-niger.org',
        'Malawi': 'http://www.nsomalawi.mw',
        'Mali': 'https://www.instat-mali.org',
        'Mauritania': 'http://ansade.mr',
        'Mauritius': 'https://statsmauritius.govmu.org',
        'Rwanda': 'https://www.statistics.gov.rw',
        'Senegal': 'http://www.ansd.sn',
        'Seychelles': 'https://www.nbs.gov.sc',
        'Sierra_Leone': 'http://www.statistics.sl',
        'South_Africa': 'http://www.statssa.gov.za/',
        'Tanzania': 'https://www.nbs.go.tz/',
        'Togo': 'https://inseed.tg',
        'Uganda': 'https://www.ubos.org',
        'Zambia': 'https://www.zamstats.gov.zm',
        'Zimbabwe': 'https://www.zimstat.co.zw',
        }

Domains = {
    'Benin': 'wwww.insae.bj',
    'Botswana': 'www.statsbots.org.bw',
    'Burkina_Faso': 'www.insd.bf',
    'Burundi': 'www.isteebu.bi',
    'Cote_dIvoire': 'www.ins.ci/',
    'Ethiopia': 'www.statsethiopia.gov.et',
    'Gambia': 'www.gbosdata.org',
    'Ghana': 'www.statsghana.gov.gh',
    'Guinee': 'www.stat-guinee.org',
    'Kenya': 'www.knbs.or.ke',
    'Namibia': 'www.nsa.org.na',
    'Niger': 'www.stat-niger.org',
    'Malawi': 'www.nsomalawi.mw',
    'Mali': 'www.instat-mali.org',
    'Mauritania': 'www.ansade.mr',
    'Mauritius': 'www.statsmauritius.govmu.org',
    'Rwanda': 'www.statistics.gov.rw',
    'Senegal': 'www.ansd.sn',
    'Seychelles': 'www.nbs.gov.sc',
    'Sierra_Leone': 'www.statistics.sl',
    'South_Africa': 'www.statssa.gov.za',
    'Tanzania': 'www.nbs.go.tz',
    'Togo': 'www.inseed.tg',
    'Uganda': 'www.ubos.org',
    'Zambia': 'www.zamstats.gov.zm',
    'Zimbabwe': 'www.zimstat.co.zw',
}


class Country(models.Model):
    name = models.CharField(max_length=120, choices=Countries)
    flag = models.ImageField(upload_to='flags', default='no_picture.png')
    url = models.URLField(max_length=200, blank=True, null=True)
    domain = models.URLField(max_length=200, blank=True, null=True)
    site = models.URLField(max_length=500, blank=True, null=True)
    check_and = models.CharField(max_length=500, blank=True, null=True)
    check_or = models.CharField(max_length=500, blank=True, null=True)

    class Meta:
        verbose_name = 'Country'
        verbose_name_plural = 'Countries'
        ordering = ['name']

    def __str__(self):
        return f'{self.name}'

    def get_absolute_url(self):
        return reverse('scraper:detail', kwargs={'pk': self.pk})

    def save(self, *args, **kwargs):
        self.url = URLs[self.name]
        self.domain = Domains[self.name]
        #self.site = sites[self.name]
        #self.check_and = check_and[self.name]
        #self.check_or = check_or[self.name]
        super().save(*args, **kwargs)


def get_upload_path(instance, filename):
    print(filename)
    file_dir = os.path.join("Data", "%s" % instance.country.name)
    full_path = os.path.join(file_dir, filename)
    return full_path


class Data(models.Model):
    country = models.ForeignKey(Country, on_delete=models.CASCADE)
    scrape_date = models.DateTimeField(auto_now_add=True)
    CPI_pdf = models.FileField(default=f'media/{country.name}/cpi.pdf', upload_to=get_upload_path, null=True, blank=True)
    CPI_doc = models.FileField(default='cpi.doc', upload_to=get_upload_path, null=True, blank=True)
    CPI_excel = models.FileField(default='cpi.xlsx', upload_to=get_upload_path, null=True, blank=True)
    report_excel = models.FileField(default='report.xlsx', upload_to=get_upload_path, null=True, blank=True)
    pdf_Filename = models.CharField(max_length=100, null=True, blank=True)
    doc_Filename = models.CharField(max_length=100, null=True, blank=True)
    excel_Filename = models.CharField(max_length=100, null=True, blank=True)
    report_Filename = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        verbose_name = 'Data'
        verbose_name_plural = 'Data'
        ordering = ['-id']
  
    # CPI_PDF_url = models.URLField(max_length=200, blank=True, null=True)
    # excel_file_name = models.FileField(default=country.name+'cpi.xlsx', upload_to=get_upload_path)
    # excel_url = models.URLField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f'{self.pdf_Filename}'

    def get_absolute_url(self):
        return reverse('scraper:country_detail', kwargs={'pk': self.pk})

    def save_pdf(self, *args, **kwargs):
        cpi_pdf = str(self.CPI_pdf).split('/')[-1]
        self.pdf_Filename = "CPI_" + cpi_pdf
        super().save(*args, **kwargs)

    def save_doc(self, *args, **kwargs):
        cpi_doc = str(self.CPI_doc).split('/')[-1]
        self.doc_Filename = "CPI_" + cpi_doc
        super().save(*args, **kwargs)

    def save_excel(self, *args, **kwargs):
        cpi_excel = str(self.CPI_excel).split('/')[-1]
        self.excel_Filename = "CPI_" + cpi_excel
        super().save(*args, **kwargs)

    def save_report(self, *args, **kwargs):
        report_excel = str(self.report_excel).split('/')[-1]
        self.report_Filename = report_excel
        super().save(*args, **kwargs)

    def month(self):
        return self.scrape_date.strftime('%B')

    def year(self):
        return self.scrape_date.strftime('%Y')


