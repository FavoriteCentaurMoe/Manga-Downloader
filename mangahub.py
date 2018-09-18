import requests
import urllib
import json
import os
import zipfile
from pathlib import Path
from bs4 import BeautifulSoup

url = 'https://mangahub.io/search?q='
historyFileName = "DownloadHistory.json"

specialCharacters = ['\\','/',':', '?', '*', '<', '>', '|']


def start():
    searchTerm = input('Enter the manga name or enter "U" to check for updates on previously updates series: ')
    if searchTerm == "U":
        test = Update()
        test.checkForUpdates()
    else:
        displayManga(makeSearchURL(searchTerm))


def displayManga(mangaURL):
    results = getSoup(mangaURL).find_all(class_="media-heading")
    if not results:
        print("No results. Try again")
        return start()
    print("{:<4} {:50} {:10} {:20}".format("#", "NAME", "CHAPTERS", "AUTHOR", ))
    num = 1
    for result in results:
        name = result.find('a').text
        try:
            author = result.find('small').text
        except AttributeError:
            author = " "
        latestChapter = result.next_sibling.find('a').text
        print("{:<4} {:50} {:10} {:20}".format(num, name, latestChapter, author))
        num += 1
    chooseManga(results)


def chooseManga(results):
    mangaChosen = input("Enter a number to select a manga or enter a name to search again : ")
    try:
        manga = results[int(mangaChosen) - 1]
        displayChapters(manga.find('a').text, manga.find('a')['href'])
    except IndexError:
        print("Index out of bounds. Try again")
        start()
    except ValueError:
        displayManga(makeSearchURL(mangaChosen))


def displayChapters(mangaName, chapterListURL):
    print(mangaName + " Chapters")
    chapters, num = getSoup(chapterListURL).find_all(class_="_287KE list-group-item"), 1
    for chapter in chapters:
        chapterNum = chapter.find(class_="text-secondary _3D1SJ").text
        print("{:<5} Chapter: {:50}".format(num, chapterNum))
        num += 1
    chooseChapters(mangaName, chapters, chapterListURL)


def chooseChapters(mangaName, chapters, chapterListURL):
    index = input("Enter 'all' for everything, a single number (5), or a range (5-7) for 5,6 and 7 : ")
    chaptersDownloaded = []
    try:
        if "all" in index:
            firstIndex = 0
            secondIndex = len(chapters)
        elif "-" in index:
            temp = index.split("-")
            firstIndex = int(temp[0]) - 1
            secondIndex = int(temp[1])
        else:
            firstIndex = int(index) - 1
            secondIndex = firstIndex + 1
        for i in range(firstIndex, secondIndex):
            try:
                chapterName = chapters[i].find('span').text
                chaptersDownloaded.append(chapterName)
                downloadChapter(mangaName, chapterName, chapters[i].find('a')['href'])
            except OSError:
                print("OSError occured at index : ", index, " on ", mangaName)
        chapterNum = chapters[firstIndex].find(class_="text-secondary _3D1SJ").text
        saveHistory(chapterNum, mangaName, chapterListURL)
    except IndexError:
        print("INDEX ERROR Invalid Format, try again")
        chooseChapters(mangaName, chapters)


def downloadChapter(mangaName, chapterName, chapterURL):
    mangaName = validName(mangaName)
    soup = getSoup(chapterURL).find_all(class_="PB0mN")[0]['src'].split('/1.')
    baseImageURL, filetype = soup[0] + "/", soup[-1]
    folder = createPath(mangaName)
    imageNames, num = [], 1
    while True:
        downloadURL = baseImageURL + str(num) + '.'
        response = isThisBroken(requests.get(downloadURL + filetype), downloadURL, filetype)
        if response.status_code != 200:
            break
        name = 'teeemp' + " " + chapterName + " " + str(num) + '.' + filetype
        imageNames.append((str(folder.resolve()) + "//" + name))
        file = folder.joinpath(name)
        with file.open('wb') as wf:
            wf.write(response.content)
        num += 1
    generateCBZ(folder, imageNames, chapterName, mangaName)


def createPath(mangaName):
    """go through the name and omit all invalid characters"""
    try:
        folder = Path(mangaName + "//")
        folder.mkdir(parents=True, exist_ok=True)
        return folder
    except NotADirectoryError:
        print(mangaName, "is an invalid file or folder name")


def validName(name):
    for character in specialCharacters:
        name = name.replace(character, ' ')
    return name


def isThisBroken(response, downloadURL, filetype):
    """checks to see if the filetpye needs to be changed"""
    if response.status_code != 200:
        return tryDifferentFileType(downloadURL, filetype)
    else:
        return response


def tryDifferentFileType(downloadURL, filetype):
    """sometimes all the images do not have the same filetype"""
    if filetype == "jpeg" or filetype == "jpg":
        filetype = "png"
    else:
        filetype = "jpeg"
    response = requests.get(downloadURL + filetype)
    if response.status_code == 404 and filetype == "jpeg":
        filetype = 'jpg'
        response = requests.get(downloadURL + filetype)
    return response


def generateCBZ(folder, imageNames, chapterName, mangaName):
    file = folder.joinpath(mangaName + " " + chapterName + ".cbz")
    if imageNames:
        z = zipfile.ZipFile(file, 'w')
        for image in imageNames:
            z.write(image)
    else:
        print("Error! No images found, CBZ not made")
    for name in imageNames:
        os.remove(name)


class Update:

    def findNewChapters(self, URL,latestChapter):
        chapters = getSoup(URL).find_all(class_="_287KE list-group-item")
        newChapters = []
        for chapter in chapters:
            chapterNum = chapter.find(class_="text-secondary _3D1SJ").text
            newChapters.append(chapter)
            if chapterNum == latestChapter:
                return newChapters

    def checkSeriesUpdates(self, num, name, content):
        latestChapter = content['Chapters']
        newChapters = self.findNewChapters(content['URL'], latestChapter)
        print(num, "  {:40} {:4} new chapters available".format(name, (len(newChapters)-1)))
        return newChapters

    def downloadChp(self, newChapters, name, URL):
        chapterNum = newChapters[0].find(class_="text-secondary _3D1SJ").text
        saveHistory(chapterNum, name, URL)
        for index in range(len(newChapters)):
            chapterName = newChapters[index].find('span').text
            chapterURL = newChapters[index].find('a')['href']
            downloadChapter(name, chapterName, chapterURL)

    def checkForUpdates(self):
        data = checkSaveData()
        newChaps = {}
        num = 1
        for d in data:
            newChaps[d] = self.checkSeriesUpdates(num, d, data[d])
            num += 1
        index = input("Enter 'all' to update all or a number to choose one series : ")
        if index == "all":
            for n in newChaps:
                self.downloadChp(newChaps[n], n, data[n]['URL'])
        else:
            try:
                n = int(index) - 1
                name = list(newChaps.keys())[n]
                self.downloadChp(newChaps[name], name, data[n]['URL'])
            except:
                print("Invalid input, try again")
                self.checkForUpdates()


def getSoup(searchURL):
    response = requests.get(searchURL)
    return BeautifulSoup(response.content, 'html.parser')


def checkSaveData():
    try:
        with open(historyFileName) as jsonFile:
            return json.load(jsonFile)
    except FileNotFoundError:
        return {}


def saveHistory(chapter, mangaName, chapterListURL):
    data = checkSaveData()
    subDict = {'Chapters':chapter, 'URL': chapterListURL}
    data[mangaName] = subDict
    with open(historyFileName, 'w') as outfile:
        json.dump(data, outfile)


def makeSearchURL(searchTerm):
    return url + urllib.parse.quote(searchTerm)


if __name__ == '__main__':
    print("Searching for manga on mangahub.io")
    start()

