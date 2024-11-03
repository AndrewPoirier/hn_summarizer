import requests
from bs4 import BeautifulSoup
from readability import Document
from datetime import datetime, timedelta
import lxml.html.clean
import json
import pickle

from llm_interface import summarize
from rss_interface import RssInterface
from article import Article
import os

# Load settings from settings.json
with open('settings.json', 'r') as f:
    settings = json.load(f)

def fetch_soup(url):
    soup = None
    
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for bad status codes
        
        soup = BeautifulSoup(response.content, 'html.parser')
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Error fetching articles from {url}: {e}")
        
    return soup

def return_articles(date, generate_summaries=True, max_articles=int(settings["max_articles"])):
    """
    Fetches and parses articles from a specified date, returning a list of Article objects.
    Args:
        date (str): The date for which to fetch articles in the format 'YYYY-MM-DD'.
        generate_summaries (bool, optional): Flag to indicate whether to generate summaries for the articles. Defaults to True.
        max_articles (int, optional): The maximum number of articles to fetch. Defaults to 30.
    Returns:
        list: A list of Article objects parsed from the fetched data.
    """
    
    articles = [] # return collection
    article_count = 0 #iterator to limit to max_articles
    
    url = settings["articles_url"] + date #build URL
    
    soup = fetch_soup(url) #get article page and convert to soup
    
    # Find all <tr> elements with class "athing"
    athing_rows = soup.find_all("tr", attrs={"class": "athing"})

    # loop through each article and parse it into an Article object
    for row in athing_rows:     
        # parse article from row   
        rank = row.find("span", attrs={"class": "rank"}).text.strip().replace(".", "")
        title = row.find("span", attrs={"class": "titleline"}).find("a").text.strip()
        article_link = row.find("span", attrs={"class": "titleline"}).find("a")["href"]
        article_id = row["id"]
        
        # the following items are in the next TR 
        score = row.next_sibling.find("span", attrs={"class": "score"}).text.strip()
        user = row.next_sibling.find("a", attrs={"class": "hnuser"}).text.strip()
        datestring = row.next_sibling.find("span", attrs={"class": "age"})["title"].split(" ")[0]
        
        # print the current item to the console
        print(f"{rank}. + {title}")
        
        # create the Article class, which will do all the heavy-lifting
        article = Article(rank, title, article_link, score, user, article_id, datestring, generate_summaries)
        
        # append the Article to the return collection
        articles.append(article)
        
        # increment the iterator
        article_count += 1
        
        # print the Article out to the console
        print(article)
        
        # check iterator for max_articles
        if article_count >= max_articles:
            break
    
    return articles

def get_date():
    """
    Returns a date string based on the settings configuration.

    If the 'override_date' key is present in the settings dictionary and has a non-empty value,
    this function returns that date. Otherwise, it returns the date for yesterday in the format 'YYYY-MM-DD'.

    Returns:
        str: The date string either from 'override_date' in settings or yesterday's date.
    """
    # prefer the override_date if one is available in settings, else return yesterday
    if "override_date" in settings and settings["override_date"] and settings["override_date"] != "":
        return settings["override_date"]
    else:
        return (datetime.now() - timedelta(1)).strftime("%Y-%m-%d")

def remove_article_by_id(article_collection, article_id):
    """
    Remove an article from the collection by its ID.

    Args:
        article_collection (list): A list of articles, where each article is an object with an 'article_id' attribute.
        article_id (int): The ID of the article to be removed.

    Returns:
        bool: True if the article was found and removed, False otherwise.

    Example:
        articles = [
            Article(article_id=1, title="First Article"),
            Article(article_id=2, title="Second Article")
        ]
        result = remove_article_by_id(articles, 1)
        # result would be True and the first article would be removed from the list.
    """
    # Iterate over the collection to find the article
    for index, article in enumerate(article_collection):
        if article.article_id == article_id:
            # Remove the article if the id matches
            del article_collection[index]
            print(f"Article with article_id {article_id} removed.")
            return True
    print(f"Article with article_id {article_id} not found.")
    return False

def trim_article_collection(articles, max_size=int(settings["max_items_to_keep"])):
    """Ensure the article collection does not exceed max_size items.

    If the number of items exceeds max_size, remove the earliest items
    until the collection size is within the limit.

    Args:
        articles (list): The collection of Article objects.
        max_size (int): The maximum allowed size of the collection.

    Returns:
        None: The function modifies the collection in place.
    """
    while len(articles) > max_size:
        articles.pop(0)  # Remove the earliest item (first in the list)
    print(f"Collection trimmed to {len(articles)} items.")
    
def log(articles):
    """
    Logs the provided articles to text files in a specified logging folder.
    This function creates a logging folder if it does not exist and writes the
    articles' details to two text files: 'output.txt' and 'pretty.txt'. The
    'output.txt' file contains a simple string representation of each article,
    while the 'pretty.txt' file contains a formatted, human-readable version
    of each article's details.
    Args:
        articles (list): A list of article objects. Each article object is
                         expected to have the following attributes:
                         - title (str): The title of the article.
                         - article_link (str): The URL link to the article.
                         - comment_link (str): The URL link to the comments.
                         - score (int): The score of the article.
                         - user (str): The user who posted the article.
                         - datestring (str): The date and time the article was posted, in the format "%Y-%m-%dT%H:%M:%S".
                         - generated_article_summary (str): The generated summary of the article.
                         - generated_comment_summary (str): The generated summary of the comments.
    Raises:
        OSError: If there is an error creating the logging folder or writing to the files.
    """
    # Create the folder path if it doesn't exist
    os.makedirs(settings["logging_folder"], exist_ok=True)

    with open(settings["logging_folder"] + "output.txt", "w") as f:
        for article in articles:
            f.write(str(article) + "\n")
            
    with open(settings["logging_folder"] + "pretty.txt", "w") as f:
        for article in articles:
            f.write(f"Title: {article.title}\n")
            f.write(f"Article Link: {article.article_link}\n")
            f.write(f"Comment Link: {article.comment_link}\n")
            f.write(f"Score: {article.score}\n")
            f.write(f"User: {article.user}\n")
            
            # Reformat the date
            date_obj = datetime.strptime(article.datestring, "%Y-%m-%dT%H:%M:%S")
            formatted_date = date_obj.strftime("%m/%d/%Y %I:%M:%S %p")
            f.write(f"Date: {article.datestring}\n")
            
            f.write(f"Generated Article Summary: {article.generated_article_summary}\n")
            f.write(f"Generated Comment Summary: {article.generated_comment_summary}\n")
            f.write("\n\n")




date = get_date()

# Load the collection from the file using pickle
with open('articles.pkl', 'rb') as file:
    articles = pickle.load(file)

# load new articles
if bool(settings["load_new_articles"]):
    articles_to_load = return_articles(date, generate_summaries=settings["generate_summaries"], max_articles=settings["max_articles"])
    for article in articles_to_load:
        remove_article_by_id(articles, article.article_id)
        articles.append(article)
    
# remove old articles over the max size limit
trim_article_collection(articles)

# persist articles to disk
with open("articles.pkl", "wb") as f:
    pickle.dump(articles, f)

print(len(articles))
log(articles)

rss = RssInterface()
rss.append_articles_to_feed(articles)
rss.save_feed()
    
    
# python3 -m http.server
# http://localhost:8000/feed.xml
# lsof -i :8000
# kill 0


    
    # TODO: RSS output or text output
    # TODO: improve comment summary to return the top 3 comments, rather than a summary. Or summaries of the top three comments?
    # TODO: handle Show|Ask|Launch HN: - don't need article plus comments, grab the OP post
    


