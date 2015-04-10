# comic scraper
import httplib2
import urllib.request
import urllib.parse
from sys import argv
import json
import pickle
import re # awaking cthulhu
import datetime
import time
import errno
import os
def datewriter(date, data):
  today_in_seconds = repr(int((time.mktime(datetime.date.today().timetuple()))*1000))
  yesterday_in_seconds = repr(int((time.mktime((datetime.date.today() - datetime.timedelta(1)).timetuple()))*1000))
  day = {}
  day['comics'] = {}
  for name in data['dates'][date]:
    day['comics'][name] = {}
    day['comics'][name]['file'] = []
    day['comics'][name]['alttxt'] = {}
    day['comics'][name]['local'] = {}
    day['comics'][name][date] = data['comics'][name][date]
    for filename in day['comics'][name][date]:
      day['comics'][name]['alttxt'][filename] = data['comics'][name]['alttxt'][filename]
      try:
        data['comics'][name]['local'][filename]
        day['comics'][name]['local'][filename] = data['comics'][name]['local'][filename]
      except:
        one = 1
    day['comics'][name]['name'] = data['comics'][name]['name']
    day['comics'][name]['url'] = data['comics'][name]['url']
    day['comics'][name]['baseurl'] = data['comics'][name]['baseurl']
  dayfile = 'day/'+date+'.json'
  try:
    os.makedirs('day')
  except:
    pass 
  if (date == today_in_seconds or date == yesterday_in_seconds):
    with open(dayfile, 'w', encoding='utf-8') as f:
      json.dump(day, f)
  else:
    try:
      with open(dayfile, 'r', encoding='utf-8') as f:
        devnull = f.read()
    except IOError:
      with open(dayfile, 'w', encoding='utf-8') as f:
        json.dump(day, f)

def write_file_of_names(comicdata):
  names = {};
  for name in comicdata:
    names[name] = {}
    names[name]['name'] = comicdata[name]['name']
  with open('names.json', 'w', encoding='utf-8') as f:
    json.dump(names, f)

def write_image_file(url, name, ret = ''):
  url = urllib.parse.urlsplit(url)
  url = list(url)
  url[2] = urllib.parse.quote(url[2])
  url = urllib.parse.urlunsplit(url)
  header_data=[('User-Agent','Mozilla/5.0')]
#  header_data=[('User-Agent','Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.2.10) Gecko/20100922 Ubuntu/10.10 (maverick) Firefox/3.6.10')]
  try:
    one = 1
    opener = urllib.request.build_opener()
    opener.addheaders = header_data
    content = opener.open(url)
    content = content.read()
    if (type(content) is not str):
      try:
        decoded = content.decode('utf-8')
      except UnicodeDecodeError:
        try:
          decoded = content.decode('windows-1252')
        except UnicodeDecodeError:
          try:
            decoded = content.decode('ascii')
          except UnicodeDecodeError:
            time_right_now = repr(int(time.mktime(time.localtime())))+datetime.datetime.now().strftime('%f')
            directory = 'strips/'+name+'/'
            imagefile = directory+time_right_now
            try:
              os.makedirs(directory)
            except:
              pass 
            try:
              with open(imagefile, 'wb') as f:
                f.write(content)
                ret = time_right_now
            except IOError:
              ret = ''
              print('fwerr: Could not write file to ' + imagefile)
            except:
              ret = ''
              print('fwerr: Un-identified error while writing file (exists?) ' + imagefile)
      except:
        ret = ''
        print(name + ': Un-identified error while trying to decode file ' + imagefile)
      if (type(decoded) is str):
        ret = ''
        print(name + ': image url returned string')
    if (ret == ''):
      os.remove(imagefile)
  except:
    pass
  return ret


def parser(comicdata, h, data):
  try:
    for date in data['dates']:
      data['dates'][date] = set(data['dates'][date])
  except KeyError:
    data['dates'] = {}
    try:
      data['comics']
    except KeyError:
      data['comics'] = {}
  for name in comicdata:
    try:
      baseurl = comicdata[name]['baseurl']
    except KeyError:
      baseurl = ""
    comic = name
    url = comicdata[name]['url']
    pattern = comicdata[name]['pattern']
    comicname = comicdata[name]['name']
    try:
      url_to_parse = comicdata[name]['feed']
    except KeyError:
      url_to_parse = url
    try:
      data['comics'][name]
    except KeyError:
      data['comics'][name] = {}
      data['comics'][name]['file'] = []
      data['comics'][name]['alttxt'] = {}
    try:
      data['comics'][name]['local']
    except KeyError:
      data['comics'][name]['local'] = {}
    data['comics'][name]['name'] = comicname
    data['comics'][name]['url'] = url
    data['comics'][name]['baseurl'] = baseurl
    header_data={'User-Agent':'Mozilla/5.0'}
#    header_data={'User-Agent':'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.2.10) Gecko/20100922 Ubuntu/10.10 (maverick) Firefox/3.6.10'}
    try:
      response, content = h.request(url_to_parse, headers=header_data)
    except httplib2.ServerNotFoundError:
      print(name + ": ERROR ServerNotFound: " + url_to_parse)
      continue
    except BaseException as e:
      try:
        errno_ = e.errno
        if errno_ == errno.ECONNRESET:
          print(name + ': reset connection')
          continue
      except:
        continue
    try:
      content_type = type(content)
    except UnboundLocalError:
      print(name + ': has no content')
      continue
    if (type(content) is not str):
      try:
        content = content.decode('utf-8')
      except UnicodeDecodeError:
        try:
          content = content.decode('windows-1252')
        except UnicodeDecodeError:
          try:
            content = content.decode('ascii')
          except UnicodeDecodeError:
            continue
    if (response.status == 200):
      match = re.search(pattern, content, re.DOTALL)
      try:
        match = match.groupdict()
      except AttributeError:
        print(name + ': No match, check regexp')
        continue
      try:
        fileurl = match['file'].rstrip('"');
      except TypeError:
        fileurl = None
      try:
        alt = match['title']
      except KeyError:
        alt = ""
      alt = re.sub("['\"]", "&#39", alt);
      if (fileurl != None):
        today_in_seconds = repr(int((time.mktime(datetime.date.today().timetuple()))*1000))
        if (fileurl not in data['comics'][name]['file']):
          data['comics'][name]['file'].append(fileurl)
          try:
            data['comics'][name][today_in_seconds] = set(data['comics'][name][today_in_seconds])
          except:
            data['comics'][name][today_in_seconds] = set()
          data['comics'][name][today_in_seconds].add(fileurl)
          data['comics'][name]['alttxt'][fileurl] = alt
          data['comics'][name][today_in_seconds] = list(data['comics'][name][today_in_seconds])
        if today_in_seconds in data['comics'][name]:
          try:
            data['dates']
          except KeyError:
            data['dates'] = {}
          try:
            data['dates'][today_in_seconds]
          except KeyError:
            data['dates'][today_in_seconds] = set()
          data['dates'][today_in_seconds].add(comic)
        if (fileurl not in data['comics'][name]['local']):
          local_file_name = ''
          local_file_name = write_image_file(data['comics'][name]['baseurl']+fileurl, name, local_file_name)
          if (local_file_name != ''):
            data['comics'][name]['local'][fileurl] = local_file_name
  for date in data['dates']:
    data['dates'][date] = list(data['dates'][date])
    datewriter(date, data)
  write_file_of_names(comicdata)
  return data;

def main():
  with open('patterns.json', 'r', encoding='utf-8') as f:
    try:
      comicdata = json.load(f)
    except IOError:
      comicdata = {}
  cachedir = '.cache'
  h = httplib2.Http(cachedir)
  try:
    jsonfile = argv[1]
  except:
    jsonfile = 'comics.json'
  data = None
  try:
    with open(jsonfile, 'r', encoding='utf-8') as f:
      jsonstr = f.read()
      if (jsonstr):
        data = json.loads(jsonstr)
  except IOError:
    data = {}
  data = parser(comicdata, h, data)
  with open(jsonfile, 'w', encoding='utf-8') as f:
    json.dump(data, f)
  
if __name__ == '__main__':
  main()
