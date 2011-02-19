import urllib, urllib2, cookielib, sys, getpass, os, unicodedata, string, time, re, demjson
from pyquery import PyQuery as pq
from lxml import etree
from urlparse import urlparse
from optparse import OptionParser

class Crawler:
	def __init__( self, address, options ):
		self.address = address
		self.options = options
		self.cookie_jar = cookielib.CookieJar()
		self.opener = urllib2.build_opener( urllib2.HTTPCookieProcessor( self.cookie_jar ) )
		urllib2.install_opener( self.opener )		
		self.headers = { "Accept" : "application/xml,application/xhtml+xml,text/html;q=0.9,text/plain;q=0.8,image/png,*/*;q=0.5", "Accept-Language" : "en-US,en;q=0.8", "User-Agent" : "Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US) AppleWebKit/534.16 (KHTML, like Gecko) Chrome/10.0.648.45 Safari/534.16" }
		self.response = None
	
	def debug( self, level, code, message ):
		if level <= int( self.options.verbose ):
			print( message )
	
	def get_address( self, page ):
		address = self.address
		page = str( page )
		if page.find("/",0,1) != -1:
			address = self.address + page
		elif page.find("http%3A//",0,9) != -1 or page.find("https%3A//",0,10) != -1:			
			address = string.replace( page, "%3A", ":" )
		elif page.find("http://",0,7) != -1 or page.find("https://",0,8) != -1:
			address = page
		elif self.response != None:
			address = self.response.geturl().rsplit("/",1)[0] + "/" + page
		return address.strip()
	
	def request( self, page, data, wrap ):		
		address = self.get_address( page )
		if data != None:
			data = urllib.urlencode( data )
		time.sleep( float( self.options.delay ) )	
		req = urllib2.Request( address, data, self.headers )
		self.debug( 3, 100, "Requesting '" + str( req.get_full_url() ) + "'" )
		try:
			self.response = urllib2.urlopen( req )
		except urllib2.URLError, e:
			print( "ERROR: " + str( getattr( e, 'code', 0 ) ) )
			print( getattr( e, 'msg', "" ) )
			print( getattr( e, 'hdrs', "" ) )
			print( getattr( e, 'fp', "" ) )
			print( getattr( e, 'filename', "" ) )
			return False
		self.html = self.response.read()
		if wrap:
			self.dom = pq( self.html )
			return self.dom	
		else:
			return self.html
		
	
	def get( self, page ):
		self.debug( 2, 101, "Sending GET request '" + page + "'" )
		return self.request( page, None, True )
		
	def post( self, page, data ):
		self.debug( 2, 102, "Sending GET request '" + page + "'" )
		return self.request( page, data, True )
		
	def rpc( self, page, data, json ):
		self.debug( 2, 103, "Sending RPC request '" + page + "'" )
		response = self.request( page, data, False )
		if json == True:
			response = demjson.decode( response )
		return response
	
	def download_binary( self, file, path, name, encode = True ):			
		if os.path.exists( path + "/" + name ) != 0:
			return True
		file_path_chunks = file.rsplit("?",1)	
		file_path = file_path_chunks[0]		
		if encode and file.find("%") == -1:					
			file_path = urllib.quote( file_path.encode("utf-8") )			
			address = self.get_address( file_path )
			try:
				address += "?" + file_path_chunks[1]
			except:
				pass
		else:
			address = self.get_address( file )
		file_name = file_path.rsplit("/",1)[1]
		if address[-1] != "/" and file_name != "" and ( self.options.crossdomain == True or file_path.find( self.address ) != -1 ):
			self.debug( 2, 104, "Downloading file '" + file + "' to '" + path + "' as '" + name + "'" )
			response = self.request( address, None, False )
			if response:
				file = open( path + "/" + name, 'wb')	
				file.write( response )
				file.close()

	
	def clean_unicode( self, data ):
		return unicodedata.normalize( 'NFKD', data ).encode( 'ASCII', 'ignore' )
	
	def clean_chars( self, data ):
		if data == None:
			return ""
		return ''.join( c for c in data if c in "-_.() %s%s" % ( string.ascii_letters, string.digits ) ).strip()
	
	def get_url_params( self, url ):
		return dict([part.split('=') for part in urlparse( url )[4].split('&')])

class MyCourses(Crawler):
	def __init__( self, address, options ):
		self.hit_code_count = 0
		self.rpc_key = None
		Crawler.__init__( self, address, options )
	
	def get( self, page ):
		return Crawler.get( self, page )
	
	def post( self, page, data ):
		return Crawler.post( self, page, data )
		
	def rpc( self, page, data, json ):
		return Crawler.rpc( self, page, data, json )
		
	def login( self, username, password ):
		login_page = self.get( "/" )
		if login_page:
			login_form = login_page( "#login_box" ).find( "form" ).eq( 0 )	
			if login_form:
				login_page = self.post( login_form.attr[ "action" ], { 'username' : username, 'password' : password } )
				if login_page:
					login_page_table = login_page.find("table#z_u")
					if login_page_table:
						self.course_links = login_page_table.find( "tr td a[title]" )
						return True
		return False
	
	def read_rpc_key( self, course ):
		for index, row in enumerate( course.find( "script" ) ):
			script = pq( row ).html()
			m = re.search( 'D2L\.Serialization\.JsonDeserializerMin\.Deserialize\((.*?),D2L.UI\);', str( script ) )
			if m:
				data_str = m.group( 1 )
				data_str = string.replace( data_str, "D2L.Notifiers.Manager.PollResult", "0" )
				data_str = string.replace( data_str, "D2L.Notifiers.Style", "0" )
				data_str = string.replace( data_str, "D2L.Notifiers.Pager.Result", "0" )
				data_str = string.replace( data_str, "D2L.Util.DateTime", "0" )
				data_str = string.replace( data_str, "D2L.Notifiers.Manager", "0" )
				data_str = string.replace( data_str, "D2L.Images.Image", "0" )
				data_str = string.replace( data_str, "D2L.Notifiers.Pager", "0" )
				data = demjson.decode( data_str )
				self.rpc_key = data[ 2 ]			
		return False
	
	def get_course_link( self, course, content ):
		content_links = course.find( "div#d_navBar a[href]" )
		for index, link in enumerate( content_links ):
			link = pq( link )
			label = link.find( "span" )
			if label and label.text() == content:
				return link.attr[ "href" ]
		return False
	
	def download_course( self, link, path ):
		course = self.get( link )
		if course:			
			self.read_rpc_key( course )
			if self.options.save_news == True:
				self.download_course_news( course, path )
			if self.options.save_content == True:
				self.download_course_content( course, path )
			if self.options.save_dropbox == True:
				self.download_course_dropbox( course, path )
			return True
		return False
	
	def download_course_dropbox( self, course, path ):
		link = self.get_course_link( course, "Dropbox" )
		if link:
			course_dropbox = self.get( link )
			if course_dropbox:
				course_dropbox_table = course_dropbox( "table#z_b" )
				if course_dropbox_table:
					course_dropbox_table_rows = course_dropbox_table.find( "tr" )					
					for index, row in enumerate( course_dropbox_table_rows ):						
						row = pq( row )
						title = None
						submission_count = None						
						if not row.attr[ "class" ]:
							dropbox_columns = row.find( "td" )
							title_cell = dropbox_columns.eq( 0 )
							submission_cell = dropbox_columns.eq( 2 )
							if title_cell:
								title = title_cell.text()
								if title_cell.find( "a" ):
									title = title_cell.find( "a" ).text()
								if title_cell.find( "label" ):
									title = title_cell.find( "label" ).eq( 0 ).text()								
							if title != None and submission_cell and submission_cell.hasClass( "d_gc" ) and submission_cell.hasClass( "d_gt" ):
								submissions_link = submission_cell.find( "a" )
								if submissions_link:
									submission_count = submissions_link.text()
									if submission_count and int( submission_count ) > 0:
										directory = path + "/Dropbox/" + self.clean_chars( title )
										if os.path.exists( directory ) == 0:
											os.makedirs( directory )										
										self.download_course_dropbox_submissions( title, submission_count, submissions_link.attr[ "href" ], directory )
					return True
		return False
	
	def download_course_dropbox_submissions( self, dropbox_folder, submission_count, link, path ):
		submissions = self.get( link )
		if submissions:
			submissions_table = submissions.find( "table#z_e" )
			if submissions_table:
				submissions_table_rows = submissions_table.find( "tr" )
				if submissions_table_rows:
					
					for index, row in enumerate( submissions_table_rows ):
						row = pq( row )
						if not row.attr[ "class" ]:
							submissions_table_columns = row.find( "td" )
							if submissions_table_columns:
								submissions_link_column = submissions_table_columns.eq( 0 )
								if submissions_link_column:
									submissions_link = submissions_link_column.find( "a" )
									if submissions_link:
										self.download_binary( submissions_link.attr[ "href" ], path, submissions_link.text(), False )
	
	def download_course_content( self, course, path ):
		link = self.get_course_link( course, "Content" )
		if link:
			course_content = self.get( link )
			if course_content:			
				course_content_table = course_content( "table#z_o" )
				if course_content_table:
					directory = path + "/Content"
					for index, row in enumerate( course_content_table.find( "td.d_gn" ) ):
						row = pq( row )						
						if os.path.exists( directory ) == 0:
							os.makedirs( directory )
						link = row.find( "a" )
						if link:
							self.download_course_content_file( course, link.attr[ "href" ], self.clean_chars( link.text() ), directory )
						else:
							directory = path + "/Content/" + self.clean_chars( row.text() )
							continue							
	
	def download_course_content_file( self, course, link, name, path ):			
		params = self.get_url_params( link )
		self.hit_code_count += 1
		timestamp = str( self.rpc_key ) + str(( time.time() + 100000000) % 100000000) + str( self.hit_code_count % 10 )
		rpc_response = self.rpc( "/d2l/lms/content/viewer/main_frame_2.d2lfile?ou=" + params[ "ou" ] + "&tId=" + params[ "tId" ] + "&d2l_body_type=1&d2l_rh=rpc&d2l_rt=call", { "params" : "{'param1':" + params[ "tId" ] + "}", "d2l_action" : "rpc", "d2l_rf" : "FetchTopicData", "d2l_hitcode" : timestamp }, True )
		if rpc_response and rpc_response[ "Result" ] and rpc_response[ "Result" ][ "Location" ]:
			extension = self.clean_chars( rpc_response[ "Result" ][ "Location" ].rsplit("?",1)[0].rsplit(".",1)[1] )
			if extension: 
				self.download_binary( rpc_response[ "Result" ][ "Location" ].strip(), path, name + "." + extension )	
	
	def download_course_news( self, course, path ):
		news_table = course("table#z_n")
		if news_table:
			if os.path.exists( path + "/News" ) == 0:
				os.makedirs( path + "/News" )
			news_table.find( "tr" )
			title = ""
			body = ""
			for index, row in enumerate( news_table.find( "tr" ) ):
				row = pq( row )
				if row.hasClass( "d_gdb" ):
					title = self.clean_chars( row.find( "label" ).text() )
					continue
				if row.hasClass( "d_gd" ):
					file = open( path + "/News/" + title + ".txt", 'w')			
					file.write( row.find( "div.D2LRichText" ).text().encode( 'ASCII', 'ignore' ) )
					file.close()
					continue
		
	def download_courses( self ):
		for index, link in enumerate( self.course_links ):
			course_link = pq( link )
			href = course_link.attr[ "href" ]
			title = self.clean_chars( course_link.text() )
			path = self.options.output
			if os.path.exists( path + "/" + title ) == 0:
				os.makedirs( path + "/" + title )
			if self.download_course( href, path + "/" + title ):
				self.debug( 0, 2, "Course '" + title + "' Successfully Saved!" )
			else:
				self.debug( 0, 0, "Course '" + title + "' Failed To Saved!" )
		

parser = OptionParser()
parser.add_option("-o", "--output", dest="output", help="dump MyCourses to DIR", metavar="DIR", default=os.getcwd()) 
parser.add_option("-v", "--verbose", dest="verbose", help="level of verbosity to use", metavar="LEVEL", default=0)
parser.add_option("-t", "--delay", dest="delay", help="seconds of delay between each request", metavar="SECONDS", default=1)
parser.add_option("-n", "--news", dest="save_news", help="save course news", action="store_true", default=False)
parser.add_option("-c", "--content", dest="save_content", help="save course content", action="store_true", default=False)
parser.add_option("-x", "--crossdomain", dest="crossdomain", help="save course content from outside of domain", action="store_true", default=False)
parser.add_option("-d", "--dropbox", dest="save_dropbox", help="save course dropbox", action="store_true", default=False)
(options, args) = parser.parse_args()

mycourses = MyCourses( "https://mycourses.rit.edu", options )
if mycourses.login( raw_input( "Username: " ), getpass.getpass( prompt='Password: ' ) ):
	mycourses.download_courses()