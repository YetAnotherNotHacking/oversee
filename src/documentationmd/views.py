documentationviews = """
# OverSee Views
In oversee, there are three main views that you are going to be interacting with. These are Map, Matrix and List,
each designed to serve a specific purpose. Knowing the purpose might help you use the program closer to how it was
intended, resulting in it being more of use to you.

## Map View
The map view is meant to emphasize the distrobution of the cameras globably, and show that on a visual map that is easy
for anyone to look at and understand the real scale of which these cameras are distributed around. In the map view, you
may notice that each of the pins on the map are clickable, clicking on a pin will bring you to the camera within the list
view of the program. In the map view, you are able to change some settings about the map, at the top right of the program's
window you are able to notice a dropdown for selecting the style of map to use, with options to choose between OpenStreetMap,
Google maps, and Google satellite data. There also is an option provided for the number of pins to load on the map, though
be cautious as the more pins that the program loads, the more processing power it takes to render each frame, and the lower
performance that you will experience in the program. To change the number of loaded pins on the map, first set the number of
pins that you would like in the entry box, and then click the Load Pins button in the GUI, and wait for the pins to load in.

## Matrix View
Matrix view is designed to prove a point just how many cameras are around the world. It is very much not as effecient as it
could be, though it is not expected to be a view that is commonly used in the program, as it might be quite overstimulating.
As for configuration options in the matrix view, you will notice that that extent of configuration is no more than a number of
threads to use for polling for images. The more threads the more changes that you will have of getting a higher count of cameras 
shown at once, though do be aware of the amount of bandwith that you are using as well as your system resources, as it is able
to use quite a lot of them. Due to lack of resources, it has not been tested the outcome of setting the number of threads higher
than the nubmer of ips in the input file, though there is no reason to seeing they will only be filling up the pool without
returning any data to the program.

## List View
List view is the most built out view in the program. It is designed for people to be able to look at invidivual cameras seperately
and for them to be able to find out information about specific cameras that they select. In the list view, you are able to notice
that there are quite a few elements, at the top of the screen you are presented with search bar, this searchbar will query the entire
endpoint, for example, if I wanted to find IP addresses starting with 79 in them, I would simply type that into the search bar, it also
works for the endpoints *without* the flags present on them. You are able to, for example, search for a certain type of camera e.g.
SnapshotJPEG in the search bar, and see all of the cameras in the list to see what cameras are using that specific type of endpoint.
Once you have finished exploring the cameras with your query, you can reset the view in the top right by clicking the Reset List button.
For each individual camera in the list, there are several options that you are able to use to explore the cameras. There are many buttons
like Favourite, Move camera, Open in browser, Get IPINFO, and Show on Map. All of these buttons are self explanatory for the most part,
but information is good so they will still be covered.  The favourite button is capable of saving cameras, though the functionality is not
fully there are the time of writing this documentation. The move camera button will open up another window, and if the camera is known
and identified as a supported camera based on it's image polling endpoint, the program will attempt to autoconfigure the movement controls
for the camera, and display buttons and status of the movement abilities of the camera for you to be able to interact with. The Open in
Browser button will simply open the home page of the camera in your internet browser. Get IPINFO will open the IP address of the camera
on a website called IP info, which is also the source of many of the locations of the ips on the map. Using that data, you are able to find
out some information about where the IP is registed (which company it gets internet from) as well as a decently accurate location of the IP.
The Show on Map button simply opens up another window with a map view widget that has a pin of the location of the camera if the program knows it,
if not, there will be a pin placed on the map explaining that there was an error when trying to load the location of the camera. You are able to
select the type of map that is shown in this map view at the top, being able to have the same selection that you have on the main map view
of the program. The final button that the program offers you is Open Stream, which simply will open the camera in another window where you 
are able to view the stream in a standalone window, with the stream automatically becoming the size of the window. You are able to view multiple
cameras this way, even being able to fullscreen the window to have a larger view of the camera if you so desire.

## Conclusion
Expore the points of the windows, and see which one interests you the most, and exlpore it. Feel free to recommend another idea that you have
for a type of view in the form of an issue on the GitHub at `https://github.com/YetAnotherNotHacking/oversee`.
"""