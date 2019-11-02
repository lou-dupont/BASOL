from os import listdir
from os.path import isfile, join
from bs4 import BeautifulSoup
import requests
import lxml.html as lh
import pandas as pd
import re
import json


def nettoyerChamp(string) :
    string = string.replace("\xa0", " ")
    string = re.sub('\s+', ' ', string)
    string = re.sub('\\.\s*$', '', string)
    string = re.sub('^ *: *', '', string)
    string = re.sub('\"', '', string)
    string = string.strip()
    return(string)

def extraireInfo(page_content, balS, chaine) :
    try : 
        info = [x for x in balS if x.text.startswith(chaine)][0]
        info = str(info.next_sibling)
        info = info.replace('<br/>', '')
        info = nettoyerChamp(info)
    except : 
        info = ''
    return(info)

def corrigerPage (page_content) : 
    raw_page = str(page_content)
   
    page_content = BeautifulSoup(raw_page, "lxml")

    for bloc in page_content.findAll('span') :
        bloc.replace_with(bloc.text)

    # Retrait des href
    for bloc in page_content.findAll(['p', 'div']):
        #if bloc.name in ('p', 'div') :
        if bloc.text.strip() == '' : 
            bloc.extract()

    # Retrait des attributs
    for bloc in page_content.findAll() :
        if bloc.name in ('input', 'table') : 
            continue
        bloc.attrs = {}

    raw_page = str(page_content)
    raw_page = re.sub(' +', ' ', raw_page)
    raw_page = re.sub("\xa0", '', raw_page)
    raw_page = re.sub("<td>\n", '<td>', raw_page)

    raw_page = re.sub('<input.*>(<strong>.*</strong>)', '\\1', raw_page)
    raw_page = re.sub('(<input([^>]*)>)\n', '\n\\1', raw_page)

    raw_page = re.sub('<td><strong>(.*)</strong>(.*)</td>', '<td>\\1\\2</td>', raw_page)
    raw_page = re.sub('(<input[^>]*>[^>]*)<br/>', '<td>\\1</td>', raw_page)
    raw_page = re.sub('<br/>(Informations complémentaires :.*)<br/>', '<br/><td>\\1</td>', raw_page)
    raw_page = re.sub('> ', '>', raw_page)
  
    page_content = BeautifulSoup(raw_page, "lxml")
    for bloc in page_content.findAll():
        if bloc.name in ('p', 'div') :
            if bloc.text.strip() == '' : 
                bloc.extract()
    raw_page = str(page_content)
    raw_page = re.sub('(<input[^>]*>[^>]*)<br/>', '<td>\\1</td>', raw_page)
    raw_page = re.sub('(<input[^>]*>[^>]*)\n', '<td>\\1</td>', raw_page)
    raw_page = re.sub('</td>\n(Autre[^>]*)\n', '</td>\n<td>\\1</td>', raw_page)
    raw_page = re.sub('(<td>.*</td>)', '\n\\1\n', raw_page)
    raw_page = re.sub('\n\n', '\n', raw_page)

    page_content = BeautifulSoup(raw_page, "lxml")

    #with open("test.html", "w") as file:
        #file.write(str(page_content))
    return(page_content)

def traiterFauxTableau (page_content, balS, chaine) :
    present = []
    tableau = [x for x in balS if x.text.startswith(chaine)][0]
    #print('--------------------------')
    #print(chaine)

    for baliseSuivante in tableau.next_elements :
        if baliseSuivante.name in ("strong", "div", "table") :
            break
        if baliseSuivante.name != 'td' : continue

        contenu = nettoyerChamp(baliseSuivante.text)
        #print('\t', contenu)

        if baliseSuivante.find('input') is None :
            texte_balise = nettoyerChamp(re.sub('.*:(.*)', '\\1', str(baliseSuivante.text)))
            if (texte_balise != '') and (not texte_balise.startswith('Aucun')) :
                present.append(texte_balise)
            continue

        elif 'checked' in baliseSuivante.find('input').attrs :
            present.append(contenu)
            continue
    return(present)

def traiterTableau (page_content, balS, chaine) :
    present = []
    #print('--------------------------')
    #print(chaine)
    tableau = [x for x in balS if x.text.startswith(chaine)][0].findNext('table')
    for td in tableau.findAll('td') :
        contenu = nettoyerChamp(td.text)
        #print('\t', contenu)
        # Cas sans input
        if td.find('input') is None :
            texte_balise = nettoyerChamp(re.sub('.*:(.*)', '\\1', str(contenu)))
            if (texte_balise != '') and (not texte_balise.startswith('Aucun')) :
                present.append(texte_balise)
            continue

        elif 'checked' in td.find('input').attrs :
            present.append(nettoyerChamp(contenu))

    return(present)

def convertirListeEnDict (liste) :
    contenu = []
    cles_dict = []
    for elem in liste : 
        contenu.append(nettoyerChamp(re.sub('(.*):(.*)', '\\2', elem)))
        cles_dict.append(nettoyerChamp(re.sub('(.*):(.*)', '\\1', elem)).replace(' ', '_'))
    dictionnaire = { cles_dict[i] : contenu[i] for i in range(0, len(contenu)) }
    return(dictionnaire)

def trouverProchainTexte(baliseDepart) : 
    balise = baliseDepart.next_sibling
    while str(balise).startswith('<br/>') : 
        balise = balise.next_sibling
    return(str(balise))

def prefixerUrl (url, prefixe) :
    if url.startswith('\\') or url.startswith('/') : 
        return(url)
    return(prefixe + url)

def allegerSection (section) : 
    cles_vides = []
    for cle in section :
        if section[cle] == '' or section[cle] == [] :
            cles_vides.append(cle)
    for cle in cles_vides : 
        del(section[cle])
    return(section)

def traiterResponsable (page_content, balS) : 
    responsable = {}

    titreRespo = [x for x in balS if x.text.startswith("Responsable")][0]
    responsable['nom_exploitant'] = nettoyerChamp(re.sub('.*:(.*)', '\\1', titreRespo.findPrevious('p').text))
    infos_respo = titreRespo.findNext('p').text.split('\n')
    infos_respo = [nettoyerChamp(x) for x in infos_respo if nettoyerChamp(x) != ""]
    try : 
        nom_responsable = nettoyerChamp(re.sub(".* :(.*)", "\\1", [x for x in infos_respo if x.startswith("Nom")][0]))
        responsable["nom_responsable_actuel_site"] = nom_responsable
    except : 
        pass
    responsable["type_responsable"] = nettoyerChamp(re.sub(".*agit(.*)", "\\1", [x for x in infos_respo if x.startswith("il s'agit")][0]))
    responsable["qualite_responsable"] = nettoyerChamp(re.sub(".*:(.*)", "\\1", [x for x in infos_respo if x.startswith("Qualité")][0]))

    return(responsable)

def traiterProprietaire (page_content, balS) :
    proprietaire = {}
    try : 
        contenu = [x for x in balS if x.text.startswith("Propriétaire")][0].findNext()
        contenu = contenu.findAll('tr')[1].findAll('td')
        contenu = [x.text for x in contenu]
        proprietaire['nom']  = contenu[0]
        proprietaire['qualite']  = contenu[1]
        if (len(contenu) == 3) :
            proprietaire['coordonnees']  = contenu[2]
        return(proprietaire)
    except : 
        return(proprietaire)

def traiterGeoreferencement (page_content) :
    georeferencement = {}
    coordonnees = []
    parcelles_cadastrales = []

    infosGeo = page_content.findAll("table", {'class': "georeferencement"})
    for infoGeo in infosGeo : 
        titre = [x.text for x in infoGeo.findAll("th")]
        contenu = [x.text for x in infoGeo.findAll("td")]

        if titre[0] == 'Référentiel' : 
            cles_dict = ['systeme', 'x', 'y', 'precision', 'precision_autre']
            ref = {cles_dict[i] : contenu[i] for i in range(0, len(contenu)) }
            coordonnees.append(ref)

        if titre[0] == 'Cadastre' :
            for infoParcelle in infoGeo.findAll('tr') :
                contenu = [x.text for x in infoParcelle.findAll("td")]
                cles_dict = ['commune', 'arrondissement', 'date', 'section', 'numero', 'precision', 'source', 'observation']
                if len(contenu)>0 :
                    parcelle = { cles_dict[i] : contenu[i] for i in range(0, len(contenu)) }
                    parcelles_cadastrales.append(parcelle)

    georeferencement['coordonnees'] = coordonnees
    georeferencement['parcelles_cadastrales'] = parcelles_cadastrales
    return(georeferencement)

def traiterEvenements (page_content, balS) :
    situation_technique = [x for x in balS if x.text.startswith("Situation technique")][1]    
    situation_technique = situation_technique.findNext('table')

    evenements = []
    cles_dict = ['type', 'date_prescription', 'etat_site', 'date_realisation']
    for evenement in situation_technique.findAll('tr')[1:] :
        contenu = evenement.findAll('td')
        contenu = [x.text for x in contenu]
        element = { cles_dict[i] : contenu[i] for i in range(0, len(contenu)) }
        evenements.append(element)
    #print(evenements)
    return(evenements)

def traiterEvenementsAutres (page_content, balS) :
    evenements_autres = [x for x in balS if x.text.startswith("Rapports sur la dépollution")][0]   
    evenements_autres = evenements_autres.findPrevious('p')
    autres = []
    for element in evenements_autres :
        if element.name ==  "strong" : break
        if str(element) == '<br/>' : continue
        autres.append(nettoyerChamp(str(element)))
    autres = [x for x in autres if x != '']  
    return(autres)

def traiterImportance (page_content, balS) : 
    importance_depot = [x for x in balS if x.text.startswith("Importance du dépôt")][0]
    importance_depot = importance_depot.findNext('table')
    contenu = [x.text for x in importance_depot.findAll('td')]
    contenu = contenu[0].split('\n') + [contenu[1]]
    contenu = [nettoyerChamp(re.sub('.*:(.*)', '\\1', x)) for x in contenu]
    cles_dict = ['tonnage_tonne', 'volume_m3', 'surface_ha', 'informations_complementaires']
    importance = { cles_dict[i] : contenu[i] for i in range(0, len(contenu)) }
    return(importance)

def traiterMesuresUrbanisme (page_content, balS) :
    dates_urbanisme = []
    documents_urbanisme = []
    balise = [x for x in balS if x.text.startswith("Mesures d'urbanisme réalisées")][0]
    for element in balise.next_elements :
        if element.name == "div" : break
        if element.name is not None : continue
        if bool(re.match(r'.*(Date|Informations).*', nettoyerChamp(element))) :
            dates_urbanisme.append(nettoyerChamp(element))
        if bool(re.match(r'.*pdf', nettoyerChamp(element))) :
            documents_urbanisme.append(nettoyerChamp(element))

    dates_urbanisme = convertirListeEnDict(dates_urbanisme)
    new_keys = {"Mesures_d'urbanisme_réalisées":'mesures_urbanisme_realisees', 
          "Date_de_l'arrêté_préfectoral":'date_arrete_prefectoral', 
          "Date_du_document_actant_le_porter_à_connaissance_risques_L121-2_code_de_l'urbanisme" : 'date_L121_2',
         "Date_du_document_actant_la_RUP" : "date_RUP",
          "Date_du_document_actant_la_RUCPE" : "date_RUCPE",
           "Informations_complémentaires" : 'informations_complementaires'}
    dates_urbanisme = dict((new_keys[key], value) for (key, value) in dates_urbanisme.items())
    documents_urbanisme = [nettoyerChamp(re.sub('.*:(.*)', '\\1', x)) for x in documents_urbanisme]
    url_arrete = "https://basol.developpement-durable.gouv.fr/tchgt/arretes-prefectoraux/"
    documents_urbanisme = [prefixerUrl(url_arrete, x) for x in documents_urbanisme]

    return([dates_urbanisme, documents_urbanisme])

def traiterSurveillance (page_content, balS) :    
    surveillance_site = {}

    surveillance_site['milieu_surveille'] = traiterFauxTableau(page_content, balS, 'Milieu surveillé')
    surveillance_site['etat'] = traiterFauxTableau(page_content, balS, 'Etat de la surveillance')

    raison_absence = page_content.find(text= "Absence de surveillance justifiée").next_element
    surveillance_site['raison_absence'] = nettoyerChamp(re.sub('.*:(.*)', '\\1', raison_absence))
    raison_report = page_content.find(text= "Surveillance différée en raison de procédure en cours").next_element
    surveillance_site['raison_report'] = nettoyerChamp(re.sub('.*:(.*)', '\\1', raison_report))

    debut_surveillance = page_content.find(text = re.compile("Début de la surveillance :"))
    surveillance_site['date_debut'] = nettoyerChamp(re.sub('.*:(.*)', '\\1', debut_surveillance))
    arret_surveillance = page_content.find(text = re.compile("Arrêt effectif de la surveillance :"))
    surveillance_site['date_arret'] = nettoyerChamp(re.sub('.*:(.*)', '\\1', arret_surveillance))
    
    resultat_surveillance = arret_surveillance.findNext(text=re.compile("Résultat de la surveillance à la date"))
    surveillance_site['resultat'] = nettoyerChamp(re.sub('.*:(.*)', '\\1', resultat_surveillance))
    surveillance_site['date_resultat'] = nettoyerChamp(re.sub('Résultat de la surveillance à la date du (.*):.*', '\\1', resultat_surveillance))
        
    resultat_surveillance_autre = page_content.find(text=re.compile("Résultat de la surveillance, autre"))    
    surveillance_site['resultat_autre'] = nettoyerChamp(re.sub('.*:(.*)', '\\1', resultat_surveillance_autre))

    return(surveillance_site)

def traiterPage (page) :
    # Lecture de la page
    raw_page = open('BASOL_pages/' + page, encoding="utf-8")
    content = BeautifulSoup(raw_page, "lxml")
    content = corrigerPage(content)
    
    # Balise
    balStrong = content.findAll('strong')

    # Elements d'informations générales
    infos = {}

    infos['region'] = extraireInfo(content, balStrong, 'Région')
    infos['code_departement'] = extraireInfo(content, balStrong, 'Département')
    infos['num_basol'] = extraireInfo(content, balStrong, 'Site BASOL numéro')
    infos['situation_technique'] = extraireInfo(content, balStrong, 'Situation technique du site')
    infos['date_publication'] = extraireInfo(content, balStrong, 'Date de publication de la fiche') 
    infos['auteur'] = extraireInfo(content, balStrong, 'Auteur de la qualification')

    #######################################################################
    ########### Localisation et identification du site
    identification = {}
    identification['nom_usuel'] = extraireInfo(content, balStrong, 'Nom usuel du site') 
    identification['localisation'] = extraireInfo(content, balStrong, 'Localisation du site') 
    identification['commune'] = extraireInfo(content, balStrong, 'Commune')
    identification['arrondissement'] = extraireInfo(content, balStrong, 'Arrondissement')
    identification['code_postal'] = extraireInfo(content, balStrong, 'Code postal')[:5]
    
    info_code_insee = extraireInfo(content, balStrong, 'Code INSEE')
    identification['code_insee'] = info_code_insee[:5]
    identification['population_code_insee'] = re.sub('.* \\((.* )ha.*\\)', '\\1', info_code_insee).replace(' ', '')   
    
    identification['adresse'] = extraireInfo(content, balStrong, 'Adresse')
    identification['lieu_dit'] = extraireInfo(content, balStrong, 'Lieu-dit')
    identification['agence_eau'] = extraireInfo(content, balStrong, "Agence de l'eau correspondante")
    
    info_UU = extraireInfo(content, balStrong, "Code géographique") 
    identification['code_geo_unite_urbaine'] = re.sub('(.*) : .*', '\\1', info_UU)
    if identification['code_geo_unite_urbaine'] == "(0 habitants)" :
        identification['code_geo_unite_urbaine'] = ""
    identification['population_unite_urbaine'] = re.sub('.*\\((.*)h.*\\)', '\\1', info_UU).replace(' ', '')
        
    # Géoréférencement, coordonnées et parcelles
    identification['georeferencement'] = allegerSection(traiterGeoreferencement(content))

    # Plan carto
    plan_carto = [j for j in balStrong if j.text.startswith('Plan(s) carto')][0]
    try : 
        url_plan = "https://basol.developpement-durable.gouv.fr/tchgt/plans-cartographiques/"
        plan_carto = plan_carto.findNext('ul').findAll('a')
        identification['url_plans_cartographiques'] = [prefixerUrl(url_plan, x.text) for x in plan_carto]
    except : 
        identification['url_plans_cartographiques'] = ""

    # Responsables et propriétaires
    identification['responsable']  = traiterResponsable(content, balStrong)
    identification['proprietaire'] = traiterProprietaire(content, balStrong)

    infos['identification'] = allegerSection(identification)
    
    #######################################################################
    ########### Caractérisation du site

    caracterisation = {}
    # Date de la caracterisation
    date = [j for j in balStrong if j.text.startswith('Caractérisation du site')][0]    
    date = re.sub('(.*) à la date du (.*)', '\\2', date.text)
    caracterisation['date'] = date
    # Descriptions
    description_site = [j for j in balStrong if j.text.startswith('Description du site')][0]
    caracterisation["description"] = nettoyerChamp(re.sub('.*:(.*)', '\\1', description_site.findParent().text))
    description_quali = [j for j in balStrong if j.text.startswith('Description qualitative')][0]  
    caracterisation["description_qualitative"] = nettoyerChamp(re.sub('.*:(.*)', '\\1', description_quali.findParent().text))


    infos['caracterisation'] = allegerSection(caracterisation)

    #######################################################################
    ########### Description site

    description = {}

    #description['origine_action'] = extraireInfo(content, balStrong, "Origine de l'action des pouvoirs publics")
    #description['date_decouverte'] = extraireInfo(content, balStrong, "Date de la découverte")
    
    description['origine_decouverte'] = traiterTableau(content, balStrong, 'Origine de la découverte')
    description['type_pollution'] = traiterTableau(content, balStrong, 'Types de pollution')
    description['origine_pollution'] = traiterFauxTableau(content, balStrong, 'Origine de la pollution')
    description['annee_vraisemblable_pollution'] = extraireInfo(content, balStrong, 'Année vraisemblable des faits')

    description['activite'] = extraireInfo(content, balStrong, 'Activité')
    description['code_activite_icpe'] = extraireInfo(content, balStrong, 'Code activité ICPE')

    infos['description']  = allegerSection(description)

    #######################################################################
    ########### Situation technique

    situation_technique_site = {}
    situation_technique_site['evenements'] = traiterEvenements(content, balStrong)
    situation_technique_site['autres_evenements'] = traiterEvenementsAutres(content, balStrong)
    
    # Rapports dépollution
    rapport = [j for j in balStrong if j.text.startswith('Rapports sur la dépollution')][0]
    try : 
        url_rapport = "https://basol.developpement-durable.gouv.fr/tchgt/documents-depollution/"
        rapport = rapport.findNext('ul').findAll('a')
        situation_technique_site['url_rapport_depollution'] = [prefixerUrl(url_rapport, x.text) for x in rapport]
    except : 
        situation_technique_site['url_rapport_depollution'] = []

    infos['details_situation_technique']  = allegerSection(situation_technique_site)

    #######################################################################
    ########### Caractérisation de l'impact
    impact = {}
    impact['dechets_identifies'] = traiterFauxTableau(content, balStrong, 'Déchets identifiés')
    impact['produits_identifies'] = traiterTableau(content, balStrong, 'Produits identifiés')
    impact['polluants_sols'] = traiterTableau(content, balStrong, 'Polluants présents dans les sols')
    impact['polluants_nappes'] = traiterTableau(content, balStrong, 'Polluants présents dans les nappes')
    impact['polluants_sols_nappes'] = traiterTableau(content, balStrong, 'Polluants présents dans les sols ou les nappes')
    impact['risques_immediats'] = traiterFauxTableau(content, balStrong, 'Risques immédiats')
    impact['importance'] = traiterImportance(content, balStrong)

    infos['impact']  = allegerSection(impact)

    #######################################################################
    ########### Environnement du site
    environnement = {}

    # Zone d'implantation
    zone = [j for j in balStrong if j.text.startswith("Zone d'implantation")][0].findPrevious('p')
    zone = re.sub('.*</strong>(<br/>|)(.*)</p>', '\\2', str(zone).lower()).split('<br/>')
    zone = [nettoyerChamp(re.sub(' : ', ' ', x)) for x in zone if x != '']
    environnement['zone'] = zone

    environnement['hydrogeologie'] = traiterTableau(content, balStrong, 'Hydrogéologie')
    environnement['utilisation_actuelle'] = traiterTableau(content, balStrong, 'Utilisation actuelle du site')
    environnement['impacts_constates'] = traiterFauxTableau(content, balStrong, 'Impacts constatés')

    infos['environnement']  = allegerSection(environnement)

    #######################################################################
    ########### Surveillance du site

    infos['surveillance']  = allegerSection(traiterSurveillance(content, balStrong))

    #######################################################################
    ########### Restriction usage et mesures urbanismes

    urbanisme = {}
    urbanisme['restriction_usage'] = traiterFauxTableau(content, balStrong, "Restriction d'usage sur")
    urbanisme['mesures'] = traiterFauxTableau(content, balStrong, "Mesures d'urbanisme réalisées")
    urbanisme['dates'] = traiterMesuresUrbanisme(content, balStrong)[0]
    urbanisme['document'] = traiterMesuresUrbanisme(content, balStrong)[1]

    infos['restriction_urbanisme'] = allegerSection(urbanisme)

    #######################################################################
    ########### Restriction usage et mesures urbanismes

    traitement = {}
    traitement['mise_en_securite'] = traiterFauxTableau(content, balStrong, "Mise en sécurité du site")
    traitement['dechets'] = traiterFauxTableau(content, balStrong, "Traitement des déchets")
    traitement['terres'] = traiterFauxTableau(content, balStrong, "Traitement des terres")
    traitement['eaux'] = traiterFauxTableau(content, balStrong, "Traitement des eaux")
    infos['traitement'] = traitement
    
    
    infos = allegerSection(infos)
    return(infos)

fiches = [f for f in listdir('BASOL_pages/') if isfile(join('BASOL_pages/', f))]

# Lecture de la page
raw_page = open('BASOL_pages/fiche_33.0042.html', encoding="utf-8")
content = BeautifulSoup(raw_page, "lxml")
content = corrigerPage(content)

responsable = {}
balStrong = content.findAll("strong")
traiterSurveillance(content, balStrong)

basol = {}
sites = []
from datetime import datetime
print(datetime.now())
i = 0
for fiche in fiches : 
    #print(fiche)
    if i % 100 == 0 : print(i)
    i = i+1
    sites.append(traiterPage(fiche))
print(datetime.now())

basol['sites'] = sites

# Sauvegarde test
with open('BASOL.json', 'w', encoding='utf-8') as outfile:
    json.dump(basol, outfile, ensure_ascii=False)
with open('BASOL_test.json', 'w', encoding='utf-8') as outfile:
    json.dump(basol['sites'][:20], outfile, ensure_ascii=False)
    
