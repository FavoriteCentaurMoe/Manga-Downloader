import requests
import urllib
import json
import os
import zipfile
from pathlib import Path
from bs4 import BeautifulSoup

url = 'https://mangahub.io/search?q='
history_file_name = "DownloadHistory.json"

special_characters = ['\\', '/', ':', '?', '*', '<', '>', '|', '"', '-']


def start():
    """Accept user input and either search for a particular title or check for updates"""
    search_term = input('Enter the manga name or enter "U" to check for updates on previously updates series: ')
    if search_term == "U":
        Update()
    else:
        MangaDownloader(search_term)
    print("Download complete!")
    start()


class MangaDownloader:

    def __init__(self, search_term):
        print("Starting with the search term")
        search_url = url + urllib.parse.quote(search_term)
        self.display_manga(search_url)

    def display_manga(self, search_url):
        """Show the user the results of the manga search"""
        manga_results = get_soup(search_url).find_all(class_="media-heading")
        try:
            assert manga_results, "No results found. Please try again"
        except AssertionError:
            print("No results found. Please try again")
            start()
        print(" {:<4} {:60} {:10} {:20}".format("#", "NAME", "CHAPTERS", "AUTHOR", ))
        for num, result in enumerate(manga_results, 1):
            name = result.find('a').text
            try:
                author = result.find('small').text
            except AttributeError:
                author = " "
            latest_chapter = result.next_sibling.find('a').text
            print(" {:<4} {:60} {:10} {:20}".format(num, name, latest_chapter, author))
        self.choose_manga(manga_results)

    def choose_manga(self, results):
        """Process input"""
        manga_chosen = input("Enter a number to select a manga or enter a name to search again : ")
        try:
            manga = results[int(manga_chosen) - 1]
            self.display_chapters(valid_name(manga.find('a').text), manga.find('a')['href'])
        except IndexError:
            print("Index out of bounds. Try again with a number below "+str(len(results)))
            start()
        except ValueError:
            search_url = url + urllib.parse.quote(manga_chosen)
            self.display_manga(search_url)

    def display_chapters(self, manga_name, chapter_list_url):
        """Display all chapters"""
        print(manga_name + " Chapters : ")
        chapters = get_soup(chapter_list_url).find_all(class_="_287KE list-group-item")
        limit = 10
        for num, chapter in enumerate(chapters, 1):
            chapter_num = chapter.find(class_="text-secondary _3D1SJ").text
            print("{:<5} Chapter: {:50}".format(num, chapter_num))
            if num == limit:
                print("Enter a space to see all results")
                user_response = MangaDownloader.chapter_input()
                if user_response == " ":  # show the rest of the results if the user presses space
                    limit += 1000
                else:
                    break

        if num < limit: # There were less entries than the limit
            user_response = MangaDownloader.chapter_input()
        self.choose_chapters(manga_name, chapters, chapter_list_url, user_response)

    @staticmethod
    def chapter_input():
        print("Enter 'all' to download all chapters")
        print("To download a specific chapters, enter single number or a range (5-7):")
        user_response = input()
        return user_response

    def choose_chapters(self, manga_name, chapters, chapter_list_url, index):
        """Process user input and begin downloading process"""
        chapters_downloaded = []
        try:
            if "all" in index:
                first_index = 0
                second_index = len(chapters)
            elif "-" in index:
                temp = index.split("-")
                first_index = int(temp[0]) - 1
                second_index = int(temp[1])
            else:
                first_index = int(index) - 1
                second_index = first_index + 1
            for i in range(first_index, second_index):
                try:
                    chapter_name = valid_name(chapters[i].find('span').text)
                    chapters_downloaded.append(chapter_name)
                    download_chapter(manga_name, chapter_name, chapters[i].find('a')['href'])
                except OSError:
                    print("OSError occurred at index : ", index, " on ", manga_name)
            chapter_num = chapters[first_index].find(class_="text-secondary _3D1SJ").text
            save_history(chapter_num, manga_name, chapter_list_url)
        except IndexError:
            print("Chapter Index Error. Invalid Format, try again")
            self.display_chapters(manga_name, chapter_list_url)

    @staticmethod
    def is_this_broken(response, download_url, filetype):
        """checks to see if the filetpye needs to be changed"""
        if response.status_code != 200:
            return MangaDownloader.try_different_file_type(download_url, filetype)
        else:
            return response

    @staticmethod
    def try_different_file_type(download_url, filetype):
        """sometimes all the images do not have the same filetype"""
        if filetype == "jpeg" or filetype == "jpg":
            filetype = "png"
        else:
            filetype = "jpeg"
        response = requests.get(download_url + filetype)
        if response.status_code == 404 and filetype == "jpeg":
            filetype = 'jpg'
            response = requests.get(download_url + filetype)
        return response


class Update:
    def __init__(self):
        print("Checking for updates")
        try:
            self.check_for_updates()
        except AssertionError:
            print("No download history was found. Look for a file named " + history_file_name)

    def check_for_updates(self):
        """Load for save data and check to see if new chapters have come out"""
        data = read_save_data()
        assert data != {}
        new_chapters = self.check_series_updates(data)
        index = input("Enter 'all' to update all or a number to choose one series : ")
        print("Index is "+index)
        if index == "all":
            for n in range(0, len(new_chapters)):
                self.download_chapter(new_chapters[n], data[new_chapters[n][0]]['URL'])
        else:
            try:
                self.download_chapter(new_chapters[int(index) - 1], data[new_chapters[int(index) - 1 ][0]]['URL'])
            except IndexError:
                print("Invalid Index! Please enter a number under " + str(len(new_chapters)))
                self.check_for_updates()

    def check_series_updates(self, data):
        """Iterate through each series in the data and check for updates"""
        new_chapter_data = []  # contains the name and list of new chapters
        for num, name in enumerate(data, 1):
            latest_chapter = data[name]['Chapters']
            new_chapter_list = self.find_new_chapters(data[name]['URL'], latest_chapter)
            print(num, " {:40} {:4} new chapters available".format(name, (len(new_chapter_list))))
            if new_chapter_list:
                new_chapter_data.append((name, new_chapter_list))
        return new_chapter_data

    def find_new_chapters(self, chapter_url, latest_chapter):
        """Iterates though all chapters and return a list of new chapters"""
        chapters = get_soup(chapter_url).find_all(class_="_287KE list-group-item")  # overall list of chapters
        new_chapters = []
        for chapter in chapters:
            chapter_num = chapter.find(class_="text-secondary _3D1SJ").text
            if chapter_num == latest_chapter:
                return new_chapters
            new_chapters.append(chapter)

    def download_chapter(self, new_chapter_data, chapter_url):
        name, new_chapter_list = new_chapter_data
        chapter_number = new_chapter_list[0].find(class_="text-secondary _3D1SJ").text
        save_history(chapter_number, name, chapter_url)
        for index in range(len(new_chapter_list)):
            chapter_name = new_chapter_list[index].find('span').text
            chapterURL = new_chapter_list[index].find('a')['href']
            download_chapter(valid_name(name), valid_name(chapter_name), chapterURL)


# Global Functions

def download_chapter(manga_name, chapter_name, chapter_url):
    """Download each image from the chapter website"""
    print("Downloading : "+chapter_name)
    soup = get_soup(chapter_url).find_all(class_="PB0mN")[0]['src'].rsplit('/1.', 1)
    base_image_url, filetype = soup[0] + "/", soup[-1]
    folder = create_path(manga_name)
    image_names, num = [], 1
    while True:
        download_url = base_image_url + str(num) + '.'
        response = MangaDownloader.is_this_broken(requests.get(download_url + filetype), download_url, filetype)
        if response.status_code != 200:
            break
        name = manga_name + " " + chapter_name + " " + str(num) + '.' + filetype
        image_names.append((str(folder.resolve()) + "/" + name))
        file = folder.joinpath(name)
        with file.open('wb') as wf:
            wf.write(response.content)
        num += 1
    generate_cbz(folder, image_names, chapter_name, manga_name)


def generate_cbz(folder, image_names, chapter_name, manga_name):
    """Compress the downloaded images into a .cbz file"""
    file = folder.joinpath(manga_name + " " + chapter_name + ".cbz")
    if image_names:
        z = zipfile.ZipFile(file, 'w')
        for image in image_names:
            z.write(image)
    else:
        print("Error! No images found, CBZ not made")
    for name in image_names:
        os.remove(name)


def create_path(manga_name):
    """Creates the downloads folder, if neccesary"""
    try:
        folder = Path("Downloads//" + manga_name + "//")
        folder.mkdir(parents=True, exist_ok=True)
        return folder
    except NotADirectoryError:
        print(manga_name, "is an invalid file or folder name")


def valid_name(name):
    """"Ensures there are no special characters present"""
    for character in special_characters:
        name = name.replace(character, '')
    return name



def get_soup(search_url):
    """Gets the html and puts it in a parser"""
    response = requests.get(search_url)
    return BeautifulSoup(response.content, 'html.parser')


def read_save_data():
    """Opens the download history file"""
    try:
        with open(history_file_name) as jsonFile:
            return json.load(jsonFile)
    except FileNotFoundError:
        return {}


def save_history(chapter, manga_name, chapter_list_url):
    data = read_save_data()
    sub_dict = {'Chapters': chapter, 'URL': chapter_list_url}
    data[manga_name] = sub_dict
    with open(history_file_name, 'w') as outfile:
        json.dump(data, outfile)
        outfile.flush()


if __name__ == '__main__':
    print("Searching for manga on mangahub.io")
    start()

