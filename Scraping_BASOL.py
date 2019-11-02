# Scraping BASOL - pollution des sols du MTES

from bs4 import BeautifulSoup
import requests
import re
import os
import urllib.request
import time

url_racine = "https://basol.developpement-durable.gouv.fr/"
url_recherche = url_racine + "resultat.php?debut=%s"

# Répertoire d'accueil des pages html
dossier = "BASOL_pages/"
if not os.path.exists(dossier): 
	os.mkdir(dossier)

# Nombre de pages de résultats
page_reponse = requests.get(url_recherche %'1', timeout=5)
page_contenu = BeautifulSoup(page_reponse.content, "html.parser")

nb_pages = page_contenu.find_all("div", {"id": "titre"})[0].text
total = int(re.search('(.*) réponses - affichage de (.*) à (.*) ', nb_pages).group(1))
pas = int(re.search('(.*) réponses - affichage de (.*) à (.*) ', nb_pages).group(3))
num_debut = [x * pas + 1 for x in list(range(total // pas + 1))]


# URL des pages de pollution
fiches = []
for num in num_debut: 
    print("Page de résultats :", num)
    page_reponse = requests.get(url_recherche%str(num), timeout=5)
    page_contenu = BeautifulSoup(page_reponse.content, "html.parser")
    liens_resultat = page_contenu.find_all("a", {"class" : "lien-resultat"})
    liens_resultat = [lien['href'] for lien in liens_resultat]
    for lien in liens_resultat:
        url_page = url_racine + lien
        numero_page = re.sub('.*sp=(.*)', 'fiche_\\1', lien)
        nom_page = dossier + numero_page + '.html'
        urllib.request.urlretrieve(url_page, nom_page)



