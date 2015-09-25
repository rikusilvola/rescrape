import httplib2
import urllib.request
import urllib.parse
from sys import argv, exit, stderr
import getopt
import json
import re # awaking cthulhu
import datetime
import time
import errno
import os
import copy

#options
_img_headers = [('User-Agent', 'Mozilla/5.0')]
_feed_headers = {'User-Agent':'Mozilla/5.0'}
_data_dir = 'data'
_img_dir = 'img'
_cache_dir = '.cache'
_pattern_json = 'patterns.json'
_input_json = ''
_output_json = ''
_meta_json = ''
_store_img = False
_no_scrape = False
_rebuild_days = False
_export_days = False
_export_meta = False
_debug = False
_mode = 0o777
_req_timeout = 3
_tries = 1
_data_key = 'data'
_meta_key = 'meta'

def initDay(date, data):
  day = {}
  day[_data_key] = {}
  for name in data['dates'][date]:
    day[_data_key][name] = {}
    day[_data_key][name]['file'] = []
    day[_data_key][name]['alttxt'] = {}
    day[_data_key][name]['local'] = {}
    day[_data_key][name][date] = []
    day[_data_key][name][date] = data[_data_key][name][date]
    for filename in day[_data_key][name][date]:
      day[_data_key][name]['alttxt'][filename] = data[_data_key][name]['alttxt'][filename]
      try:
        data[_data_key][name]['local'][filename]
        day[_data_key][name]['local'][filename] = data[_data_key][name]['local'][filename]
      except KeyError: # no local file
        pass
    day[_data_key][name]['name'] = data[_data_key][name]['name']
    day[_data_key][name]['url'] = data[_data_key][name]['url']
    day[_data_key][name]['baseurl'] = data[_data_key][name]['baseurl']
  return day

def export_daydata(date, data):
  today_in_seconds = repr(int((time.mktime(datetime.date.today().timetuple()))*1000))
  yesterday_in_seconds = repr(int((time.mktime((datetime.date.today() - datetime.timedelta(1)).timetuple()))*1000))
  # consider reading current json file to detect changes
  day = initDay(date, data)
  daydir = _data_dir + '/days/'
  dayfile = daydir + date + '.json'
  if os.path.isdir(daydir) == False: # create directories if not existing
    try:
      os.makedirs(daydir)
    except IOError as e:
      print('Cannot create day directory', file=stderr)
      if _debug:
        print(e, file=stderr)
  # always update last two dates
  if (_rebuild_days or date == today_in_seconds or date == yesterday_in_seconds):
    with open(dayfile, 'w', encoding='utf-8') as f:
      json.dump(day, f)
  else:
    # create older if not existing
    try:
      with open(dayfile, 'r', encoding='utf-8') as f:
        devnull = f.read()
    except IOError:
      with open(dayfile, 'w', encoding='utf-8') as f:
        json.dump(day, f)

def export_metadata(data):
  names = {};
  names[_meta_key] = {}
  for name in data:
    names[_meta_key][name] = {}
    names[_meta_key][name]['name'] = data[name]['name']
    try:
      names[_meta_key][name]['last'] = data[name]['last']
    except KeyError:
      names[_meta_key][name]['last'] = 0
  return names

def sanitize_url(url):
  url = urllib.parse.urlsplit(url)
  url = list(url)
  if (url[0] == ''): #scheme
    url[0] = 'http'
  url[2] = urllib.parse.quote(url[2])
  url = urllib.parse.urlunsplit(url)
  return url

def decode_to_str(content, suggestion = ''):
  codes = ['utf-8', 'windows-1252', 'ascii']
  try:
    content_type = type(content)
  except UnboundLocalError:
    print(e, ": " + name + ' has no content', file=stderr)
    return ''
  if content_type is not str:
    if suggestion != '':
      try:
        content = content.decode(suggestion)
        return content
      except UnicodeDecodeError as e:
        if _debug:
          print(e + ": Suggested decoding not succesful.", file=stderr)
        pass
    for code in codes:
      if code == suggestion:
        continue
      try:
        content = content.decode(code)
        break # not reached if decode not succesful
      except UnicodeDecodeError as e:
        if _debug:
          print(e + ": Content not encoded with " + code, file=stderr)
        continue
  return content

def replace_file(directory, filename, content, binary = True):
  full_path = directory + filename
  write_mode = 'wb' if binary else 'w'
  if os.path.isdir(directory) == False: # create directories if not existing
    try:
      os.makedirs(directory, _mode)
    except IOError as e:
      print('Cannot create img directory', file=stderr)
      if _debug:
        print(e, file=stderr)
      return False
  if os.path.exists(full_path): # try to remove first
    try:
      os.remove(full_path)
    except: # raised if not a file or on windows if file in use
      pass
  try:
    with open(full_path, write_mode) as f:
      f.write(content)
  except IOError as e:
    print('fwerr: Could not write file to ' + full_path, file=stderr)
    if (_debug):
      print(e, file=stderr)
    return False
  except Exception as e:
    print('fwerr: Un-identified error while writing file (exists?) ' + full_path, file=stderr)
    if (_debug):
      print(e, file=stderr)
    return False
  return True

def write_image_file(ref, url, name, filename = ''):
  url = sanitize_url(url)
  try:
    opener = urllib.request.build_opener()
    header = _img_headers[0:]
    header.append(('Referer', ref)) # add refer to get passed referer checks
    opener.addheaders = header
    resource = opener.open(url)
    content = resource.read()
    if content:
      if "image" in resource.info()['Content-Type'] and type(content) is not str:
        decoded = content
      else:
        decoded = decode_to_str(content) # try to see if content can be decoded to str
      if (type(decoded) is not str):     # decoding was unsuccesful
        directory = _img_dir + '/' + name + '/'
        if filename == '' or os.path.exists(directory + filename) == False:
          filename = repr(int(time.mktime(time.localtime())))+datetime.datetime.now().strftime('%f')
        if replace_file(directory, filename, content, True) == False:
          filename = ''
      else:
        print(name + ': image url returned string', file=stderr)
  except Exception as e:
    print("Unknown error while getting image file for " + name, file=stderr)
    if _debug:
      print(e, file=stderr)
    pass
  finally:
    return filename

def init_data(data, patterns):
  keys = ['file', 'alttxt', 'local', 'last']
  objs = {'file': [], 'alttxt': {}, 'local': {}, 'last': 0}
  try:
    for date in data['dates']: # remove duplicates
      data['dates'][date] = set(data['dates'][date])
  except KeyError:
    data['dates'] = {}
    try:
      data[_data_key]
    except KeyError:
      data[_data_key] = {}
  for name in patterns:
    try:
      data[_data_key][name]
    except KeyError:
      data[_data_key][name] = {}
    for key in keys: # init key if not exist
      try:
        data[_data_key][name][key]
      except KeyError:
        data[_data_key][name][key] = copy.deepcopy(objs[key]) # create a copy of the object, not the reference
    try:
      baseurl = patterns[name]['baseurl']
    except KeyError:
      baseurl = ""
    data[_data_key][name]['baseurl'] = baseurl
    data[_data_key][name]['url'] = patterns[name]['url']
    data[_data_key][name]['name'] = patterns[name]['name']
  return data

def httplib2_request(h, url_to_parse):
  n = 0
  while n < _tries:
    try:
      response, content = None, None # request timeout returns nothing
      response, content = h.request(url_to_parse, headers=_feed_headers) #httplib2 takes dictionary of headers
    except httplib2.ServerNotFoundError as e:
      print(name + " ServerNotFound: " + url_to_parse, file=stderr)
      if _debug:
        print(e, file=stderr)
      return None, None
    except KeyboardInterrupt: # why does this make it work?
      exit(1)
    except BaseException as e:
      try:
        errno_ = e.errno
        if errno_ == errno.ECONNRESET:
          print('Connection reset', file=stderr)
          return None, None
      except NameError as e:
        if _debug:
          print("Unknown request error", file=stderr)
          print(e, file=stderr)
        return None, None
    if response == None:
      n += 1
      print('Connection timeout ' + str(n), file=stderr)
    else:
      return response, content
  return response, content

def process_match(match, data, name):
  try:
    fileurl = match['file'].rstrip('"');
  except TypeError:
    fileurl = None
  try:
    alt = match['title']
  except KeyError:
    alt = ""
  alt = re.sub("['\"]", "&#39", alt);
  if fileurl != None:
    today_in_seconds = repr(int((time.mktime(datetime.date.today().timetuple()))*1000))
    if fileurl not in data[_data_key][name]['file']:
      data[_data_key][name]['file'].append(fileurl)
      data[_data_key][name]['alttxt'][fileurl] = alt
      data[_data_key][name]['last'] = today_in_seconds
      try:
        data[_data_key][name][today_in_seconds] = set(data[_data_key][name][today_in_seconds])
      except KeyError:
        data[_data_key][name][today_in_seconds] = set()
      data[_data_key][name][today_in_seconds].add(fileurl)
      data[_data_key][name][today_in_seconds] = list(data[_data_key][name][today_in_seconds])
    if today_in_seconds in data[_data_key][name]:
      try:
        data['dates'][today_in_seconds]
      except KeyError:
        data['dates'][today_in_seconds] = set()
      data['dates'][today_in_seconds].add(name)
    if _store_img and fileurl not in data[_data_key][name]['local']:
      local_file_name = write_image_file(url_to_parse, data[_data_key][name]['baseurl'] + fileurl, name)
      if local_file_name != '':
        data[_data_key][name]['local'][fileurl] = local_file_name
  return data

def parser(patterns, h, data):
  data = init_data(data, patterns)
  for name in patterns:
    pattern = patterns[name]['pattern']
    url = patterns[name]['url']
    try:
      url_to_parse = patterns[name]['feed']
    except KeyError:
      url_to_parse = url
    try:
      offset = patterns[name]['offset']
    except KeyError:
      offset = 0
    try:
      count = patterns[name]['count']
    except KeyError:
      count = 1
    try:
      step = patterns[name]['step']
    except KeyError:
      step = 1
    if step == 0 or count == 0:
      print("Malformed pattern for " + name + ". Step and count cannot be 0")
      exit(2)
#    print("Requesting " + url_to_parse + " for " + name)
    response, content = httplib2_request(h, url_to_parse)
    if response == None:
      continue
    if (response.status == 200):
      content = decode_to_str(content)
      if content == '' or type(content) is not str:
        print("Unable to decode page for " + name, file=stderr)
        continue
      matches = list(re.finditer(pattern, content, re.DOTALL))
      if len(matches) == 0:
        print(name + ': No match, check regexp', file=stderr)
        continue
      if count < 0 or count+offset >= len(matches):
        t = len(matches)
      else:
        t = count+offset
      if step < 0:
        offset = -offset-1
        t = -t-1
      r = range(offset, t, step)
      for index in r:
        try:
          match = matches[index].groupdict()
        except AttributeError:
          break
        print(match['file'])
        data = process_match(match, data, name)
    else:
        print(name + ': Error response ' + str(response.status))
  try:
    data['dates']
    for date in data['dates']: # set -> list as set is not serializable
      data['dates'][date] = list(data['dates'][date])
      if _export_days:
        export_daydata(date, data)
  except KeyError: # no dates
    pass
  return data;

def usage():
  print( 'usage: rescrape.py [options] ... '
      '[-p pattern-file | -i input-file | -o output-file]\n'
      '-h, --help               : print this message\n'
      '-p, --pattern-file=file  : specify pattern file\n'
      '-i, --input=file         : specify input file\n'
      '-o, --output=file        : specify output file\n'
      '--io file                : specify input-output file\n'
      '--data-dir=path          : specify directory to write json files to\n'
      '--cache-dir=path         : specify directory to write caches to\n'
      '-l, --store-local-copy   : store local copy of matched images\n'
      '--img-dir=path           : specify directory to write image files to\n'
      '--rebuild-image-db       : redownload all images\n'
      '-d, --export-days        : export days to separate json files\n'
      '--rebuild-days           : rebuild all day files\n'
      '-m, --export-meta        : export meta data\n'
      '--meta-file=file         : specify output meta data file\n'
      '--no-scrape              : do not scrape\n'
      )

def readArgs(args):
  try:
    opts, args = getopt.getopt(args, "hp:i:o:mdl", ["help", "pattern-file=", "input=", "output=", "io=", "export-days", "rebuild-days", "img-dir=", "data-dir=", "cache-dir=", "debug", "export-meta", "meta-file=", "no-scrape", "store-local-copy", "rebuild-image-db", "dk="])
  except getopt.GetoptError:
    usage()
    exit(2)
  global _input_json
  global _output_json
  global _pattern_json
  global _export_days
  global _export_meta
  global _meta_json
  global _rebuild_days
  global _img_dir
  global _data_dir
  global _cache_dir
  global _debug
  global _no_scrape
  global _store_img
  global _data_key
  for opt, arg in opts:
    if opt in ("-h", "--help"):
      usage()
      exit(2)
    elif opt == "--dk":
      _data_key = arg
    elif opt == "--io":
      _input_json = arg
      _output_json = arg
    elif opt in ("-i", "--input"):
      _input_json = arg
    elif opt in ("-o", "--output"):
      _output_json = arg
    elif opt in ("-p", "--pattern-file"):
      _pattern_json = arg
    elif opt in ("-d", "--export-days"):
      _export_days = True
    elif opt in ("-m", "--export-meta"):
      _export_meta = True
    elif opt == "--meta-file":
      _export_meta = True
      _meta_json = arg
    elif opt == "--rebuild-days":
      _rebuild_days = True
    elif opt == "--img-dir":
      _store_img = True
      _img_dir = arg
    elif opt == "--data-dir":
      _data_dir = arg
    elif opt == "--cache-dir":
      _cache_dir = arg
    elif opt == "--debug":
      _debug = True
    elif opt == "--no-scrape":
      _no_scrape = True
    elif opt in ("-l", "--store-local-copy"):
      _store_img = True
    elif opt == "--rebuild-image-db":
      print("Rebuilding image db not implemented")
      exit(2)
  if _debug:
    print('Options:\n'
        '_input_json : "'   + _input_json + '"\n'
        '_output_json : "'  + _output_json + '"\n'
        '_pattern_json : "' + _pattern_json + '"\n'
        '_export_days : '   + str(_export_days) + '\n'
        '_rebuild_days : '  + str(_rebuild_days) + '\n'
        '_store_img: '      + str(_store_img) + '\n'
        '_img_dir : "'      + _img_dir + '"\n'
        '_data_dir : "'     + _data_dir + '"\n'
        '_cache_dir : "'    + _cache_dir + '"\n'
        '_no_scrape : "'    + str(_no_scrape) + '"\n'
        '_export_meta : "'  + str(_export_meta) + '"\n'
        '_meta_json : "'    + _meta_json + '"\n'
        '_debug : "'        + str(_debug) + '"\n')

def main():
  readArgs(argv[1:])
  if _data_key == _meta_key:
    print("_data_key cannot be identical with _meta_key", file=stderr)
    exit(2)
  try:
    with open(_pattern_json, 'r', encoding='utf-8') as f:
      try:
        patterns = json.load(f)
      except Exception as e:
        print("Malformed pattern file, exiting...", file=stderr)
        if (_debug):
          print(e, file=stderr)
        exit(2)
  except IOError as e:
    if _no_scrape: # no need for patterns if not scraping
      pass
    else:
      print("Pattern file not found, exiting...", file=stderr)
      if (_debug):
        print(e, file=stderr)
      exit(2)
  data = {}
  if _input_json != '':
    try:
      with open(_input_json, 'r', encoding='utf-8') as f:
        jsonstr = f.read()
        if (jsonstr):
          try:
            data = json.loads(jsonstr)
          except Exception as e:
            print("Malformed input file, exiting...", file=stderr)
            if (_debug):
              print(e, file=stderr)
            exit(2)
    except IOError as e:
      print("Input file not found, exiting...", file=stderr)
      if (_debug):
        print(e, file=stderr)
      exit(2)
  h = httplib2.Http(_cache_dir, timeout=_req_timeout)
  if _no_scrape == False:
    data = parser(patterns, h, data)
  if _export_meta:
    meta = export_metadata(data[_data_key])
    if _meta_json != '':
      try:
        with open(_meta_json, 'w', encoding='utf-8') as f:
          json.dump(meta, f)
      except IOError as e:
        print("Cannot write to meta file", file=stderr)
        if (_debug):
          print(e, file=stderr)
        exit(1)
    else: #default to stdout
      print(json.dumps(meta))
  if _no_scrape == False: # only write data out if scraped
    if _output_json != '':
      try:
        with open(_output_json, 'w', encoding='utf-8') as f:
          json.dump(data, f)
      except IOError as e:
        print("Cannot write to output file", file=stderr)
        if (_debug):
          print(e, file=stderr)
        exit(1)
    else:
      print(json.dumps(data))

if __name__ == '__main__':
  main()
