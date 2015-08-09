#!/usr/bin/env python

# krill - the hacker's way of keeping up with the world
#
# Copyright (c) 2015 Philipp Emanuel Weidmann <pew@worldwidemann.com>
#
# Nemo vir est qui mundum non reddat meliorem.
#
# Released under the terms of the GNU General Public License, version 3
# (https://gnu.org/licenses/gpl.html)


try:
    # Python 3
    from urllib.request import urlopen
except ImportError:
    # Python 2
    from urllib2 import urlopen

import re
import sys
import time
import codecs
import argparse
import calendar
from datetime import datetime
from collections import namedtuple

import feedparser
from bs4 import BeautifulSoup
from blessings import Terminal



StreamItem = namedtuple("StreamItem", ["source", "time", "title", "text", "link"])



class StreamParser:
    def _html_to_text(self, html):
        # Hack to prevent Beautiful Soup from collapsing space-keeping tags
        # until no whitespace remains at all
        html = re.sub("<(br|p|li)", " \\g<0>", html, flags=re.IGNORECASE)
        text = BeautifulSoup(html, "html.parser").get_text()
        # Idea from http://stackoverflow.com/a/1546251
        return " ".join(text.strip().split())


    def get_tweets(self, html):
        document = BeautifulSoup(html, "html.parser")

        for tweet in document.find_all("p", class_="tweet-text"):
            header = tweet.find_previous("div", class_="stream-item-header")

            name = header.find("strong", class_="fullname").string
            username = header.find("span", class_="username").b.string

            time_string = header.find("span", class_="_timestamp")["data-time"]
            time = datetime.fromtimestamp(int(time_string))

            # For Python 2 and 3 compatibility
            to_unicode = unicode if sys.version_info[0] < 3 else str
            # Remove ellipsis characters added by Twitter
            text = self._html_to_text(to_unicode(tweet).replace(u"\u2026", ""))

            link = "https://twitter.com%s" % header.find("a", class_="tweet-timestamp")["href"]

            yield StreamItem("%s (@%s)" % (name, username), time, None, text, link)


    def get_feed_items(self, xml, url):
        feed_data = feedparser.parse(xml)
        # Default to feed URL if no title element is present
        feed_title = feed_data.feed.get("title", url)

        for entry in feed_data.entries:
            time = datetime.fromtimestamp(calendar.timegm(entry.published_parsed)) \
                   if "published_parsed" in entry else None
            title = entry.get("title")
            text = self._html_to_text(entry.description) if "description" in entry else None
            link = entry.get("link")

            # Some feeds put the text in the title element
            if text is None and title is not None:
                text = title
                title = None

            # At least one element must contain text for the item to be useful
            if title or text or link:
                yield StreamItem(feed_title, time, title, text, link)



class TextExcerpter:
    # Clips the text to the position succeeding the first whitespace string
    def _clip_left(self, text):
        return re.sub("^\S*\s*", "", text, 1)


    # Clips the text to the position preceding the last whitespace string
    def _clip_right(self, text):
        return re.sub("\s*\S*$", "", text, 1)


    # Returns a portion of text at most max_length in length
    # and containing the first match of pattern, if specified
    def get_excerpt(self, text, max_length, pattern=None):
        if len(text) <= max_length:
            return text, False, False

        if pattern is None or not pattern.search(text):
            return self._clip_right(text[0:max_length]), False, True
        else:
            match = pattern.search(text)
            start, end = match.span()
            match_text = match.group()
            remaining_length = max_length - len(match_text)
            if remaining_length <= 0:
                # Matches are never clipped
                return match_text

            excerpt_start = max(start - (remaining_length // 2), 0)
            excerpt_end = min(end + (remaining_length - (start - excerpt_start)), len(text))
            # Adjust start of excerpt in case the string after the match was too short
            excerpt_start = max(excerpt_end - max_length, 0)
            excerpt = text[excerpt_start:excerpt_end]
            if excerpt_start > 0:
                excerpt = self._clip_left(excerpt)
            if excerpt_end < len(text):
                excerpt = self._clip_right(excerpt)

            return excerpt, excerpt_start > 0, excerpt_end < len(text)



class Application:
    _known_items = set()


    def __init__(self, args):
        self.args = args


    def _print_error(self, error):
        print("")
        print(Terminal().bright_red(error))


    def _get_stream_items(self, url):
        try:
            data = urlopen(url).read()
        except Exception as error:
            self._print_error("Unable to retrieve data from URL '%s': %s" % (url, str(error)))
            # The problem might be temporary, so we do not exit
            return list()

        parser = StreamParser()
        if "//twitter.com/" in url:
            return parser.get_tweets(data)
        else:
            return parser.get_feed_items(data, url)


    def _read_file(self, filename):
        try:
            with open(filename, "r") as myfile:
                lines = [line.strip() for line in myfile.readlines()]
        except Exception as error:
            self._print_error("Unable to read file '%s': %s" % (filename, str(error)))
            sys.exit(1)

        # Discard empty lines and comments
        return [line for line in lines if line and not line.startswith("#")]


    # Extracts feed URLs from an OPML file (https://en.wikipedia.org/wiki/OPML)
    def _read_opml_file(self, filename):
        try:
            with open(filename, "r") as myfile:
                opml = myfile.read()
        except Exception as error:
            self._print_error("Unable to read file '%s': %s" % (filename, str(error)))
            sys.exit(1)

        return [match.group(2).strip() for match in
                re.finditer("xmlUrl\s*=\s*([\"'])(.*?)\\1", opml, flags=re.IGNORECASE)]


    def _highlight_pattern(self, text, pattern, pattern_style, text_style=None):
        if pattern is None:
            return text if text_style is None else text_style(text)
        if text_style is None:
            return pattern.sub(pattern_style("\\g<0>"), text)
        return text_style(pattern.sub(pattern_style("\\g<0>") + text_style, text))


    def _print_stream_item(self, item, pattern=None):
        print("")

        term = Terminal()
        time_label = " on %s at %s" % (term.yellow(item.time.strftime("%a, %d %b %Y")),
                                       term.yellow(item.time.strftime("%H:%M"))) \
                     if item.time is not None else ""
        print("%s%s:" % (term.cyan(item.source), time_label))

        if item.title is not None:
            print("   %s" % self._highlight_pattern(item.title, pattern,
                                                    term.bold_black_on_bright_yellow, term.bold))

        if item.text is not None:
            excerpter = TextExcerpter()
            excerpt, clipped_left, clipped_right = excerpter.get_excerpt(item.text, 220, pattern)

            # Hashtag or mention
            excerpt = re.sub("(?<!\w)([#@])(\w+)",
                             term.green("\\g<1>") + term.bright_green("\\g<2>"), excerpt)
            # URL in one of the forms commonly encountered on the web
            excerpt = re.sub("(\w+://)?[\w.-]+\.[a-zA-Z]{2,4}(?(1)|/)[\w#?&=%/:.-]*",
                             term.bright_magenta_underline("\\g<0>"), excerpt)

            # TODO: This can break previously applied highlighting (e.g. URLs)
            excerpt = self._highlight_pattern(excerpt, pattern, term.black_on_bright_yellow)

            print("   %s%s%s" % ("... " if clipped_left else "", excerpt,
                                 " ..." if clipped_right else ""))

        if item.link is not None:
            print("   %s" % self._highlight_pattern(item.link, pattern,
                                                    term.black_on_bright_yellow_underline,
                                                    term.bright_blue_underline))


    def update(self):
        # Reload sources and filters to allow for live editing
        sources = list()
        if self.args.sources is not None:
            sources.extend(self.args.sources)
        if self.args.sources_file is not None:
            if self.args.sources_file.endswith(".opml"):
                sources.extend(self._read_opml_file(self.args.sources_file))
            else:
                sources.extend(self._read_file(self.args.sources_file))
        if not sources:
            self._print_error("No source specifications found")
            sys.exit(1)

        filters = list()
        if self.args.filters is not None:
            filters.extend(self.args.filters)
        if self.args.filters_file is not None:
            filters.extend(self._read_file(self.args.filters_file))

        patterns = list()
        for filter_string in filters:
            try:
                patterns.append(re.compile(filter_string, re.IGNORECASE))
            except Exception as error:
                self._print_error("Error while compiling regular expression '%s': %s" %
                                  (filter_string, str(error)))
                sys.exit(1)

        items = list()
        def add_item(item, pattern=None):
            item_id = (item.source, item.link)
            if item_id in self._known_items:
                # Do not print an item more than once
                return
            self._known_items.add(item_id)
            items.append((item, pattern))

        for source in sources:
            for item in self._get_stream_items(source):
                if patterns:
                    for pattern in patterns:
                        if (item.title is not None and pattern.search(item.title)) or \
                           (item.text is not None and pattern.search(item.text)) or \
                           (item.link is not None and pattern.search(item.link)):
                            add_item(item, pattern)
                            break
                else:
                    # No filter patterns specified; simply print all items
                    add_item(item)

        # Print latest news last
        items.sort(key=lambda item: datetime.now() if item[0].time is None else item[0].time)

        for item in items:
            self._print_stream_item(item[0], item[1])


    def run(self):
        term = Terminal()
        print("%s (%s)" % (term.bold("krill 0.2.0"),
                           term.underline("https://github.com/p-e-w/krill")))

        while True:
            try:
                self.update()
                if self.args.update_interval <= 0:
                    break
                time.sleep(self.args.update_interval)
            except KeyboardInterrupt:
                # Do not print stacktrace if user exits with Ctrl+C
                sys.exit()



def main():
    # Force UTF-8 encoding for stdout as we will be printing Unicode characters
    # which will fail with a UnicodeEncodeError if the encoding is not set,
    # e.g. because stdout is being piped.
    # See http://www.macfreek.nl/memory/Encoding_of_Python_stdout and
    # http://stackoverflow.com/a/4546129 for extensive discussions of the issue.
    if sys.stdout.encoding != "UTF-8":
        # For Python 2 and 3 compatibility
        prev_stdout = sys.stdout if sys.version_info[0] < 3 else sys.stdout.buffer
        sys.stdout = codecs.getwriter("utf-8")(prev_stdout)

    arg_parser = argparse.ArgumentParser(prog="krill", description="Read and filter web feeds.")
    arg_parser.add_argument("-s", "--sources", nargs="+",
            help="URLs to pull data from", metavar="URL")
    arg_parser.add_argument("-S", "--sources-file",
            help="file from which to load source URLs " +
                 "(OPML format assumed if filename ends with \".opml\")", metavar="FILE")
    arg_parser.add_argument("-f", "--filters", nargs="+",
            help="patterns used to select feed items to print", metavar="REGEX")
    arg_parser.add_argument("-F", "--filters-file",
            help="file from which to load filter patterns", metavar="FILE")
    arg_parser.add_argument("-u", "--update-interval", default=300, type=int,
            help="time between successive feed updates " +
                 "(default: 300 seconds, 0 for single pull only)", metavar="SECONDS")
    args = arg_parser.parse_args()

    if args.sources is None and args.sources_file is None:
        arg_parser.error("either a source URL (-s) or a sources file (-S) must be given")

    Application(args).run()



if __name__ == "__main__":
    main()
