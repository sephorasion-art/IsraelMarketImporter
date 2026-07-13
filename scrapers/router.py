from scrapers import tavliney


def importer(url):

    if "tavlineypereg.co.il" in url:
        return tavliney.scraper(url)

    raise Exception("Fournisseur non supporté")