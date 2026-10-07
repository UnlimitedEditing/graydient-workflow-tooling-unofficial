# Graydient API — Notes From the Support Channel

Distilled from a 3-file, ~2,100-message Telegram export of Graydient's API support group. Filtered deterministically (not by manually reading the whole export) down to substantive technical messages from the ~10 people who actually answer API questions in that channel: tlack, Captain, Russ, Ape Agent, Hassan Raza, KV, P., V, J, Red.

Raw export lived at `ChatExport_2026-07-23/` and is intentionally excluded from version control (large, mostly noise, and contains other users' messages/tokens) — this file is the extracted signal.


## tlack (105 messages)

- (11.09.2023 02:59:37 UTC+02:00) hmm, though i think the command will technically work in the prompt (with init_image) - there is no way to supply a url to grab the face from i need to give you access to the user upload api to do this, i think (i presume you are familiar with the telegram-based procedure)

- (11.09.2023 16:58:06 UTC+02:00) should work with init_image and prompt = " /facelift " - let me know if not

- (11.09.2023 17:18:42 UTC+02:00) Sorry, that was missing in docs. Added! https://app.graydient.ai/api-help/ Also, concepts API call now returns is_nsfw and example_url

- (11.09.2023 17:19:32 UTC+02:00) Here's an example of the Curl "data" element doing a remix via API: -d '{"init_image":"https://piratediffusion1.s3.amazonaws.com/renders2/GenwpW/00001-v-pro-6958889.jpg","num_images":3,"prompt":"/remix test shoe /images:1","callback_url":"http://mockbin.org/bin/ea76f93c-7fb1-4082-947f-a1336d213247"}'

- (13.09.2023 02:07:55 UTC+02:00) The mask_image can now be supplied via mask_image parameter. Don't forget to supply an init_image as well.

- (13.09.2023 16:29:14 UTC+02:00) Telegram does not provide a way for us to associate meta-data to something that has been posted/uploaded by bot But we wanted to implement rich reply-to-edit and other reply-oriented commands, which by necessity needed to understand exactly which image the person is referencing These captions allow us to see what is being replied to and figure out which prompt or image it is The 130s is the total time taken from initial prompt to final finished set of images - in the future we are going to transition this to initial wait time, instead of total time. I believe you also receive this in "elapsed" field in Webhook POST data (rABC1) is the render "hash code" (encrypted row id of "render" / prompt data) (iXYZ2) is the image hash code (encrypted row id of image)

- (28.09.2023 00:41:35 UTC+02:00) Ok, I created a new group for the monitoring of your bot and made the correct database associations. Please send through a test render and lets see if it pops up! I'll remove myself once its working. Also, I repaired the rembg support in API. Just add /bg to the start of your prompt.

- (28.09.2023 02:42:18 UTC+02:00) make whole lines of themed trinkets with just an inspired prompt

- (28.09.2023 04:32:15 UTC+02:00) no, same issue as controlnet. i will have a fix this week.

- (28.09.2023 04:32:30 UTC+02:00) (there is no way to specify the controlnet control image url)

- (28.09.2023 04:53:42 UTC+02:00) you should use one of those prompt gallery sites like CivitAI and try to pick up what successful prompts look like. it should usually show you the loras used but maybe sometimes not? let me know if it seems like a bug. i would say - be very verbose, be precise, use many visual keywords, each one steers the algorithm in one direction - use a good base model, use a suitable lora, use a negative ti its a big question though. maybe also ask in Prompt Engineering room

- (28.09.2023 05:22:09 UTC+02:00) if you view it on the web you can see the prompt history tree and click each render?

- (29.09.2023 03:16:51 UTC+02:00) It would be best to get it in API Here is my current to-do list which we will knock out before Monday: 1) support for supplying a URL as a controlnet control image and faceswap 2) usage measurement 3) recipe dump Am I missing anything?

- (13.10.2023 17:24:13 UTC+02:00) This chat group is related to our AI image rendering API: https://graydientplatform.com/

- (02.12.2023 19:57:17 UTC+02:00) Hi Hakan. We offer an open ended API and reskinnable white label interface. We can also consult to bring new features to life. What specifically would you like to know?

- (28.12.2023 04:39:57 UTC+02:00) You can use /blend or /faceswap or controlnet to achieve something similar depending on what you are trying to do (pull in references from other images)

- (28.12.2023 04:43:18 UTC+02:00) yep all commands that work via prompt should work via api its an option, not a command based on IP Adapters if you wanna understand the underlying tech

- (28.12.2023 04:45:42 UTC+02:00) no, you should just do /render /blend:URL444 prompt... init_image is only the input for *the task itself*; arguments given to a prompt like controlnet or blend wont ever use init_image perhaps tricky to understand but simple in practice check out this message i am replying to which gives a good example of how to use placeholder URLs for stuff like this

- (28.12.2023 04:46:04 UTC+02:00) the two-step controlnet process that we have is only for customer convenience; its not really needed for the API i.e., in telegram, its a little hard to attach an image and explain that its an option for the /edges option, but not the /blend option, ya know? and then to have to reuse the same ones over and over so we name them and refer to them

- (28.12.2023 04:53:29 UTC+02:00) its hard to say. you need numerous photos to create new images via a fine tuned model. o use blend or faceswap you only need one, but, you have less capability of controlling the overall output - lets say face vs clothing. i would say making a custom model is the best route if you can check all the boxes as for requirements

- (28.12.2023 04:55:40 UTC+02:00) Yes, but the API use restriction should be gone in a few days. (Made a lot of progress on it, still more to do) The SDXL thing - I have no idea when they might fix that, seems obvious to me But don't underestimate the difficulty of finding 50 good images of someone and entering GOOD captions for them Ponder doing that on a wide scale basis and calculate the effort required

- (09.01.2024 20:13:42 UTC+02:00) num_images problem - what type of tasks are you dispatching? i can look into it. in the meantime just throw /images :1 in your prompt or w/e and it should work reliably

- (08.05.2024 17:34:26 UTC+02:00) thank you! please tell your cool friends about our platform. as for your question: you can create as many as you want. you can use them via API or WebUI or Telegram - so you can build your bot persona into a larger program if you are so inclined There's a topic in the VIP Support channel about Polly bots if you wanna delve in more or take our convo there

- (05.06.2024 21:58:31 UTC+02:00) Not easily. Our API doesn't provide the OpenAI-standard API endpoint because we do so much preparation and condition on the input. Your best bet would be use to DeepInfra.com for their hosted OpenAI API

- (12.06.2024 01:57:00 UTC+02:00) Yep, you can do /highdef in the API to apply that process. Set the init_image to the original image

- (08.07.2024 20:11:00 UTC+02:00) yes, you can supply it as /images :n as part of your prompt, or supply an "options" field with those parameters along with your prompt and use /images :n in there instead

- (08.07.2024 20:11:27 UTC+02:00) all of the "regular" option commands work via the API, so its just like using it via Telegram. perfect your prompt there, then transfer to api call

- (08.07.2024 20:12:23 UTC+02:00) precisely! here's our more-or-less-up-to-date reference, just in case: https://piratediffusion.com/cheat-sheet/ the only thing to keep in mind is that reply-based commands require the initial image to be provided as "init_image" in request parameter body

- (08.07.2024 20:17:26 UTC+02:00) we do not retry at this time, but if you record the render hashes as you receive them from the render call, you can later check status we beg you to not poll for status if you have any other option

- (08.07.2024 20:19:19 UTC+02:00) typical render request, let's say two images in SDXL, takes 20-40 seconds, but during high load can spike.. for guidance about tuning your queue

- (08.07.2024 20:20:06 UTC+02:00) our api should respond very quickly so if you have a time critical loop you could set a timeout of, say, 5 seconds for the initial API call and probably never reach the failure case

- (17.07.2024 21:29:28 UTC+02:00) due to the cost involved to us making that lora the API isnt explained publicly - i will message you

- (20.07.2024 00:44:09 UTC+02:00) Img2img yes. We have faceswap as well. You could do Instance ID by making a ComfyUI Workflow, adding it to our system, then calling via API

- (20.07.2024 00:48:10 UTC+02:00) ComfyUI is a world unto itself. Very powerful system. With our API its the easiest way to run it. start here I guess: https://www.reddit.com/r/comfyui/ you can find premade workflows for Instant ID but if you cant tinker around in Comfy to play with it first its gonna be hard to setup on our system (just cuz some comfy knowledge is required)

- (20.07.2024 00:56:34 UTC+02:00) an request can take up to a minute or two to render when you do an API call, you're not setup to wait a minute or two - HTTP calls time out so, when the images are done, our server POSTs a message to your server when you do a request to render something, you provide the URL to that server you cant turn the iphone into the server in that respect

- (20.07.2024 01:03:13 UTC+02:00) consider building your app around a chatbot experience to impress GenZers and bored investors. we provide complete capability to integrate a chatbot you define on your own via API

- (20.07.2024 01:05:22 UTC+02:00) 👍 look into our remix operation, very flexible. can also use /blend for ipadapters or controlnet depending on what kinda img2img you are trying to do

- (20.07.2024 01:12:34 UTC+02:00) one important thing to keep in mind while you're playing on Telegram, trying things out and rendering images, our system will fill in random values for anything you dont specify In the case of img2img, the right STRENGTH setting (aka denoising strength on other platforms) is vital - this number tells the AI how much its allowed to change the image a high number like 0.9 means it will change almost everything about the picture too low and you wont get the change you want it may seem easy to pick the right number, but it isnt imagine the person has an image of the snowy swiss alps they prompt "hell" in your img2img interface without a very high strength setting, the AI will have a very hard time changing the alps into the firey pits of hell but, with a high strength setting, you won't "see" much of the original image in the new one the right number varies prompt-to-prompt and with each image our system is tuned to produce a few different images in one batch, with different strength settings (and guidance, etc) and let the user pick the best option many AI apps generate a single image at a time, but its hard to know what the right settings are, which makes people sit there forever re-rendering while "chimping" values to try to find the right mix of 10 different sliders - quite painful i'd say just a thought

- (20.07.2024 01:21:03 UTC+02:00) If you want to lock in that face thing we have an image description endpoint that can return either a text description or bounding boxes of objects found in the image (model = Florence2) - can send details. This is a nice extra and allows your backend to have some real intelligence further down the line. i.e., - landscape? do this transformation, apply these tags to platform post..

- (20.07.2024 01:27:41 UTC+02:00) literally zero people have asked for that feature in the API so far, if anyone is keeping score

- (20.07.2024 22:10:26 UTC+02:00) It starts with a good working workflow: Our interactive mode is only for debugging right now. (Soon you will be able to buy credits to go interactive for X amount of time.) Once you have a working ComfyUI workflow you want to import, type /workflows - there is a link at the top that wil take you to the workflows manager, where you can define a new workflow and link fields from the graydient equivalent ( /steps ) to ComfyUI nodes (KSampler > Steps) There's a Graydient workflow guide document that I'm trying to find the link to, explains things a bit better.

- (20.07.2024 23:26:48 UTC+02:00) Comfy is a whole thing unto itself - and to attach it to an API you can call easily involves supplying a few key details. Alas, custom race cars don't come with cupholders! P.s. Linky here: https://docs.google.com/document/d/1x8J_2JBYOzzjNAhXIE7L_u7QSjXjsEYnxrygvc5XT5c/edit?usp=sharing

- (30.07.2024 01:51:16 UTC+02:00) Ah this does seem cool, would make a great workflow.

- (30.07.2024 01:54:28 UTC+02:00) it looks like the model would work populated into our workflow system 👍 we allow you to populate the URLs of required models as part of the setup process

- (04.11.2024 17:30:27 UTC+02:00) Howdy! Was afk yesterday attempting to take a mental health day. Indeed, init_image is correct! Perhaps the reason for the failure is something else. I can't say I've tried Imgur URLs before. If you PM me one of the render hashes or the full request details I may be able to track down what happened better I've attached a screenshot of a Curl request that does a simple highdef upscaling task.. seems to be similar to what you are doing p.s. base64 encoding the init image does make some sense especially for non-internet-hosted stuff but we would have to add that feature

- (04.11.2024 22:13:01 UTC+02:00) I think I see the problem. The URL appears to be URL encoded. Since we're using a JSON body here, you don't need to escape / encode the colons (:) slashes (/) etc Also in this example you put init_image_filename but just init_Image should do - those other alternatives were incorrect and from our Workflows system, not our rendering API (sorry)

- (07.11.2024 08:30:22 UTC+02:00) hey TJ just do something like $ cat create-render-workflow.sh TOKEN=`cat token-dev.txt` curl -v \ http://localhost:26403/api/v3/render \ -X POST \ -H "Content-Type: application/vnd.api+json" \ -H "Accept: application/vnd.api+json" \ -H "Authorization: Bearer $TOKEN" \ -d '{"options":"/workflow /run:basicflow3", "prompt":"ugly guy", "callback_url":"https://femdragon.free.beeceptor.com/render"}'

- (07.11.2024 08:33:21 UTC+02:00) so just update the workflow details there in the "options" part

- (07.11.2024 08:33:53 UTC+02:00) yep, with python + requests you'll probably be building that up as a lil dictionary to send over - add your workflow name to the options field there

- (07.11.2024 18:26:54 UTC+02:00) PNGs and JPGs are "nominally" 72dpi the stable diffusion 1.5 series of models internally outputs only 512x512, so if you go much higher (say, double it), you'll get repeated characters and content in your generated image SDXL and flux are internally 1024 so if you need a higher number of pixels i would render at the native size and upscale

- (08.11.2024 05:11:45 UTC+02:00) it's possible. check out my curl example from around 20 hours ago in this chat. you just put the command in there as you would w/ telegram

- (06.01.2025 18:41:50 UTC+02:00) you're basically correct! a few little notes: 1. you need both the regular workflow JSON file and the "API json file" that you can get by turning on developer tools in the ComfyUI settings 2. i'll send you both json files for that workflow; you then need to map the fields and supply concept data as needed 3. just for reference, you can export a "backup file" which contains both forms of the workflow json, plus all the field and data mappings - this is useful to batch together all the settings all at once. i'll send you all three variants via PM, give me a few minutes

- (19.01.2025 23:45:52 UTC+02:00) right now, we allow simultaneous renders for API clients. but, truthfully, some have abused this privilege we're considering at a model where users who need that can pay per render, whereas occasional users, hobbyists and pro-ams can pay the same low all inclusive monthly fee so, if you see your workloads as being massive parallel, we may not be the right choice but if you are doing slow-paced or interactive renders via API, and want to use it interactively as well, it's a good fit

- (16.02.2025 17:49:58 UTC+02:00) Put negative part in square brackets inside prompt string

- (25.02.2025 07:45:15 UTC+02:00) for every user, definitely not. we do numeric calculations to estimate our cost per render and price our plans according to a percentile and histogram of how users use our system some users cost us a fortune and pay too little, otehrs pay a lot and don't hammer the system that much. for us it seems to even out, and we believe that all-inclusive is a good niche - i personally worryingly staring at my credit balance and doing that weird "well it was $25 for 500, but i only paid $17, so that means that this 4.89 credits costs me... uhhh.." which i am constantly experiencing on pay per use services financially the wisest thing? no. finding a product-market niche? yes!

- (25.02.2025 07:46:08 UTC+02:00) no, our larger integrations pay a per-render amount beyond a certain point. captain can provide the details, im just a coder

- (26.02.2025 18:51:25 UTC+02:00) yes, an API key can be used to render stuff for different people but soon we are going to rework the plans so that personal use within reasonable limits is OK on personal plans, and commercial use for paying customers goes to a pay-per-render type setup this should remove any confusion about how much is "too much" for an API key

- (26.02.2025 18:58:02 UTC+02:00) yeah, we have a queue of stuff to render when you're in the web or telegram system, it checks the queue if you already have something in there and complains if you're using it via the API endpoint, it just puts it in the queue regardless of whats in there already then work is dispatched in order from that queue

- (16.03.2025 08:11:54 UTC+02:00) Just put the exact command like /wf /run :name in the options field and the details in the prompt field - use /image1 :URL1 etc to fill in source images

- (16.03.2025 08:13:09 UTC+02:00) Will try to reproduce but I think you need init_image

- (17.03.2025 08:24:00 UTC+02:00) On the Graydient side, yes. You can do something like /render blah blah blah /project:xyz

- (17.03.2025 11:13:03 UTC+02:00) yes. put the options in the "options" field (eg /workflow /run :flux /size :...) and the prompt part in "prompt" (eg "A highly aesthetic photograph of..")

- (22.03.2025 18:34:01 UTC+02:00) @Lucariolucario55 please render in your private convo with @PirateDiffusion_bot cuz there are 100 people here who may not be as interested :)

- (22.03.2025 19:23:13 UTC+02:00) The render hash should be in the first response from the api when you issue the initial request - somewhere in the data element of the response dictionary I spent some time yesterday changing the api so it can optionally do a long polling / server sent events response - to get the finished product back without needing a callback url or to poll the response status over and over. Should simplify things if your http client supports it. Not ready yet but hopefully soon.

- (05.06.2025 18:37:14 UTC+02:00) via API you can do almost anything available on our platform - if you poke around in the docs you should get a better sense of it. our workflow system allows you to use anything thats available in ComfyUI, and workflows in turn are available via API we can generate videos generate images generate sounds - music right now, but text to speech should be easy and doable we don't have any sound understanding or video understanding what specifically did you want to do?

- (05.06.2025 19:33:43 UTC+02:00) That sounds really cool. What’s your orchestration system like? We are setting up a system to tie into other commercial providers from the same API. But it’s not ready yet

- (05.06.2025 21:37:28 UTC+02:00) That’s cool and very ambitious. Your n8n construction must be pretty elaborate. And impressive when you view it zoomed out :) I don’t think we can help with much of that right now unless you could see it all running through Comfy processes. If you check back in a few weeks we should have a better story regarding moving some of your side bits into one API

- (05.06.2025 21:58:44 UTC+02:00) The render endpoint covers pretty much everything, all different types of "generation" If you join I can show you how to see the list of workflows and models - I don't think those are available publicly. Then we can refund you if its not to your liking..

- (21.06.2025 17:28:21 UTC+02:00) you can start on the pro plan, we just limit you to one simultaneous request at a time, which is lifted in the business API setup. but feel free to muck around. Russ is right that, if this is a real business for you, you definitely want a server-side piece of your own creation to track user activity and actually correspond with the Graydient API. the Graydient API posts back to your server to let you know status. you'll want a database on that server so you can figure out what users are doing, show them their most recent works, allow their sessions to occur from numerous devices, etc. your app would then communicate solely with that service, in whatever way you define, not with ours directly

- (21.06.2025 17:39:02 UTC+02:00) its almost impossible to get anyone to check out a new "Just render a picture!" service there are literally thousands and it takes about 2 hours for someone to start a new one find a niche or specialization or dont bother imho

- (21.06.2025 17:52:07 UTC+02:00) I would say, find your tribe, think about the stuff you want to render.. if you are into scifi, make a scifi social media app, where people who love scifi can bond over generated images, dont just sell a text box w/ a price tag attached

- (21.06.2025 17:56:52 UTC+02:00) play with our API via a program on your regular computer. see how it works. understand the limitations. while you're doing that, think about who you are, what you want the world to look like, how you think people are hurting out there and how you can make that hurt a little less, think about what you would be proud to tell your parents you did, what you could chat with your friends about and get them just as fired up

- (21.06.2025 18:00:49 UTC+02:00) you should find the api to be no problem, i can supply "curl" scripts to illustrate most features. PM me if you get lost i am sometimes not monitoring this channel

- (21.06.2025 18:10:37 UTC+02:00) TOKEN=`cat token-live.txt` curl -vvvv \ https://app.graydient.ai/api/v3/render/ \ -X POST \ -H "Content-Type: application/vnd.api+json" \ -H "Accept: application/vnd.api+json" \ -H "Authorization: Bearer $TOKEN" \ -d '{"prompt":"/render test shoe /images:1", "callback_url":"https://femdragon.free.beeceptor.com"}'

- (14.07.2025 21:45:05 UTC+02:00) Hey guys, Added knowledge bases to the system. We're still working on the supporting materials and official announcement about this, but I wanted to invite any interested developers in here to give it a beta test. This set of features allow you to index a set of pages (crawling and link discovery happens automatically) or individual facts, and then perform semantic search on them, or have short conversations with an LLM agent that can search your documents for you and provide answers. In the background, the system is generating question and answer pairs about your content, to ease the agent's job, to supplement your own content, and to aide in downstream tasks. Uses of this information include building out new help experiences or support pages, semantic search, outlines for other content.. We hesitated for a long time in building this feature, but as we expand our in-bot help offerings, we decided it was worth the effort to finally build out something tangible, based on our learnings in the vector/embedding search and agentic bot space. But as I set about implementing it for our help system, I realized how many other not-AI-enhanced search experiences are in our system and how important this piece could be. Concept listings, workflow discovery, finding your own renders.. So I wanted to open it up and let anyone on our dev platform give it a go. Heavy usage may have to incur some kind of usage cost after the beta is completed, but that information is TBD. Anyway, long rant over - if you are interested in trying this out for something in your problem domain, PM me.

- (21.07.2025 20:14:48 UTC+02:00) you can use the API but not for a commercial product - one render at a time limitation. in other words, personal use or batch stuff only. we are going to setup pay as you go so you can do unlimited simultaneous renders to power a different product but its not available yet plus includes api yup you can use the polly endpoint unlimited, but not direct LLM, although i want to improve/fix that and provide an OpenAI-compatible endpoint i have just added a vector db feature which works over API as well - we are using it to build out our own help (RAG-ish) setup. we call it "knowledge bases". since we dont know what kind of server resources its going to require its free for now, but if you are wanting to index millions of documents, i cant guarantee it will stay free forever right now it doesnt support indexing images in the vector db but thats on my to-do list as well

- (21.07.2025 22:17:39 UTC+02:00) no, that's fine. what i mean is you cant run a startup with tons of users using our service as the backend. but if you were making something commercial, that's fine - as long as it doesnt involve more than one simultaneous render (same as our regular plan limits basically).. which basically means you having users on your own service thats hitting ours for every command they issue would overwhelm our system and isnt feasible in the limits of our $50-ish plus plan

- (22.07.2025 19:17:14 UTC+02:00) right now we don't read PDFs, although i have thought about that and have used Docling to do that in the past, so i guess its not a big leap to add it 🤔 but if you had a set of text files or webpages to index, i think it would work we do allow you to "chat" with your documents using a built in instruction prompt, and you can add personality prompts to it as well. in my limited testing so far, it didn't really seem to pick up much of the personality, but maybe i missed some details. the system automatically generates question and answer pairs for the content you put in as well, which aides in the search and chat process if you want to PM me we can setup a little test

- (19.10.2025 03:50:51 UTC+02:00) Are you activated on Telegram? If so, just type /api to @PirateDiffusion_bot and it will send you an autologin link to get to your token page

- (06.11.2025 19:30:28 UTC+02:00) for what its worth, in our DB, I checked this render hash, and I do see a media file generated Rendering videos takes about 3 times longer than images - up to 3 minutes (!!!) - so are you sure you are waiting long enough before checking status? Also, you may already know this, but in the "images" array, you'll find a subitem called "media" that contains the video file itself

- (14.01.2026 23:57:56 UTC+02:00) Ok, I'll beef that up. Clarification of knowledge base "domains": Each instance of a knowledge base - i.e., each "database" - is called a domain. It's not related to an internet domain name in any way. The person whose token created the knowledge base is considered the "owner" of the domain The domain ownership checks are to prevent user A from deleting user B's knowledge bases

- (15.01.2026 07:56:20 UTC+02:00) I just updated the docs with full Knowledge Base examples and request/response data - also updated some verbiage in the render response part. let me know if they are helpful / accurate http://my.graydient.ai/api-help

- (13.03.2026 20:26:02 UTC+02:00) its best to get the prompt first on telegram so you can be sure its correct in this case i think you want /workflow /run:wanimate-replace /image1:URL1 [DESCRIPTION] if you arent comfortable with running it via telegram, you can try a prompt in the unified render system, and at the bottom there is a foldout that gives you the text-equivalent prompt

- (13.03.2026 21:26:54 UTC+02:00) BTW, API enjoyers: Skills are available via the API as well, but the interface is private while we (😅 Russ 😅) detect and iron out some final bugs. If anyone wants to play with skills in their own app, PM me for details

- (20.03.2026 19:59:17 UTC+02:00) are you trying your prompts via tg/unified before using via API? removes a lot of guess work blend2-flux requires init_image

- (20.03.2026 20:17:32 UTC+02:00) if your telegram bot is activated, find three pictures and do this: paste first picture into telegram chat, use caption /upload /new:myimage1 paste second picture into telegram chat, use caption /upload /new:myimage2 now you have two images stored in our machine with names - this is equivalent to "placeholders" and "URL1" etc. now, paste third picture, and use caption /wf /run:blend2-flux /image1:myimage1 /image2:myimage2 Put these images together and make it look cool this paste-and-reply thing is what underlies the init_image concept - specifying starting image

- (27.03.2026 17:32:47 UTC+02:00) Describe is just a command in our system, not available via API. I suggest using vision model like Qwen 3-VL

- (27.03.2026 17:59:32 UTC+02:00) The bot persona is usable via API but it doesn't have "image input" into its queries, if that makes sense. It doesn't have the harness to use an image that way

- (29.04.2026 16:34:09 UTC+02:00) Most people use POST https://app.graydient.ai/api/v3/render/ but they should be equivalent

- (30.04.2026 04:39:56 UTC+02:00) should be about 25 seconds for SDXL, 45-60 seconds for image-based workflows, 70-100 seconds for videos give or take of course, our system load does vary. you can see the average time at the moment by using /ping . this is an average across all types of renders so it can depend on whether people are rendering videos or images etc. from an ops perspective, we get involved if the render time trends over 100 for prolonged periods. 3 mins definitely unusual check the /size you are using as well. for videos in particular that can greatly slow down the rendering process. it really depends on what types of renders you are doing but often you can find a faster approach to a similar result with some research. always try your prompts here on telegram first to observe their characteristics before integrating with your api. are you using the websocket to view events as they happen?

- (30.04.2026 04:47:18 UTC+02:00) i see an average time of about 80 seconds for that workflow. 97 seconds is a lot less than 3 minutes btw :)

- (30.04.2026 04:47:51 UTC+02:00) ah ok so three minutes for the skills part, then the render

- (30.04.2026 04:49:18 UTC+02:00) for any workflow you may want to use, try doing /wf /show:ernie (etc) - it will show you average render time if you dont need the complex diagraming and instruction following capabilities you may be able to find a faster one

- (30.04.2026 04:49:51 UTC+02:00) thats a product feature decision if you know exactly what kind of prompt you want, no need for a skill if you want the system to "fill in the blanks" - either pick a workflow/skill, or fill in a better prompt from what the user wanted - then a skill is ideal

- (30.04.2026 04:53:35 UTC+02:00) i am seeking lower TPS with deepseek-v4-flash, but then again, openrouter TPS seems to only consider *generation* speed, not prompt parsing speed; in the case of skills, we are mostly generation. i will swap it out in a few and the whole world can be our guinea pig.

- (30.04.2026 05:04:23 UTC+02:00) i personally am not 100% sure which are fastest you could investigate each one with /wf /show:... but we dont have a display that is sorted by average rendering time. i will think about a good way to show that, cuz it is interesting to think about. if you type /leaderboard it will take you to a global usage leaderboard where you can see which workflows are most popular and maybe start there. regarding the interface between skills and workflows - you can always use a specific skill instead of the two-step auto skill selection -> command generation process if you know what workflow you want to target

- (09.05.2026 19:06:44 UTC+02:00) our faceswap doesnt support masks but we do have some workflows that can combine multiple images using instructions, you may have some luck there

- (09.05.2026 20:06:33 UTC+02:00) In the prompt you send to these workflows, be sure you refer to the image subjects as "image1", "image2", etc. "image2 is wearing a black sweater and standing next to image3" and prompts like that have worked well for me in the past. i believe there are differences in the specifics between models, and we have many, but this might be a starting point for each workflow, you can do /wf /show:.. to see if there is some more documentation you can also try to find huggingface or github page for underlying model structure, it might have more specific examples in particular, i have found words like "the man is standing next to the woman" presupposes that it has noticed that /image1:.. is a man and /image2:.. is a woman, which i do not think is a step in the way these models work

- (18.05.2026 21:49:20 UTC+02:00) try putting "sync=true" in your request and you'll get the response inline but i think a bigger problem is that chatbots cant see the contents of images - they dont use the vision language model aspect but, we do have a different api endpoint that should be able to handle that for you: $ cat describe-florence-caption.sh TOKEN=`cat token-dev.txt` URL="https%3A%2F%2Fpiratediffusion1.s3.amazonaws.com%2Frenders2%2FP8W8xG%2F00001-tls-pro-g6.png" curl -v \ https://app.graydient.ai/api/v3/describe/florence/caption/$URL \ -H "Content-Type: application/vnd.api+json" \ -H "Accept: application/vnd.api+json" \ -H "Authorization: Bearer $TOKEN" \

- (19.05.2026 17:15:56 UTC+02:00) Yes, the skills API is available. See here - https://app.graydient.ai/api-help/#skills Colors are off on this page will fix later

- (25.06.2026 21:09:47 UTC+02:00) thats a skill. use the skill API part of the system

- (25.06.2026 21:10:35 UTC+02:00) Yup: https://app.graydient.ai/api-help/#skills

- (05.07.2026 01:33:24 UTC+02:00) Hi Kent We offer a "white label" type experience where you point your domain to us and you can customize the look and feel with CSS and content block drop-ins. This is the easiest way to get setup, but you have limited control over tweaking the UI to do what you want. We also have an API which you can use to develop your own frontend that targets our rendering pipeline and can support all of the functionality we offer our users. This requires you to do some coding and UI work but gives you a lot more control over the process p.s. It's a holiday here so might take a little longer than usual to get back to you :)

- (05.07.2026 04:25:34 UTC+02:00) You can't create the bot via the API, but you can interact with it. They can render images etc.

- (17.07.2026 18:14:34 UTC+02:00) seeing an odd set of errors from qwen-consistence-2 in these - was this working reliably via telegram? when making a new workflow / tweaking it i would recommend doing it from telegram (and factoring in 5-10 minutes for the workflow to reinstall on each rendering node after making a change - so testing is slow)


## Captain (63 messages)

- (09.09.2023 12:13:57 UTC+02:00) ok great, here's a token you can use in the meantime (removed)

- (09.09.2023 12:26:49 UTC+02:00) the page will have a few token tests from hassan and I, we'll clean those out

- (13.09.2023 08:19:35 UTC+02:00) not exactly but a little bit, they might be using a different base model or another lora the prompt could be something like /render /seed : 2194857008 /sampler :k_euler_a /guidance :7 /steps :30 /size :1024x1024 #sdxl ((detailed realistic illustration)) gray t-shirt design, sticker of a (((wolf head))) looking at viewer, mouth closed, yellow eyes, iconic, tshirt design, t-shirt-design [[[sports logo, mascot, sporty, athletic, body, legs, arms, feet]]] <tshirt-pod-xl> <dreamshaper1-xl>

- (13.09.2023 08:22:13 UTC+02:00) no problem! if the yellow is too much it can probably removed with the negative prompt

- (13.09.2023 08:31:43 UTC+02:00) <verybad-negative> ( inversion ) by frequent-flyer token: verybadimagenegative\_v1.3 from https://civitai.com/models/11772/verybadimagenegative to use: /render <verybad-negative> playing on a sunny day tags: -negatives description: Very Bad Negative by Yunleme is a powerful general purpose details fixer. Usage: [<verybad-negative:-1>] view gallery on web: https://debug.graydient.ai/concept/verybad-negative model family: SD15 example: https://www.graydient.ai/wp-content/uploads/2023/07/verbad.jpg more info: https://civitai.com/models/11772/verybadimagenegative

- (13.09.2023 08:32:09 UTC+02:00) <easy-negative> ( inversion ) by frequent-flyer token: easynegative from https://civitai.com/models/7808/easynegative to use: /render <easy-negative> playing on a sunny day tags: -negatives, detailers description: Easy Negative by Havok is a general quality booster. Use it in your negative prompt like this: [<easy-negative:-1>] view gallery on web: https://debug.graydient.ai/concept/easy-negative model family: SD15 example: https://www.graydient.ai/wp-content/uploads/2023/07/easy-negative-1.jpg more info: https://civitai.com/models/7808/easynegative

- (13.09.2023 08:35:35 UTC+02:00) <negative-hands> ( inversion ) by frequent-flyer token: negative\_hand-neg from https://civitai.com/models/56519/negativehand-negative-embedding to use: /render <negative-hands> playing on a sunny day tags: -negatives description: Negative Hand by Nerfgun3 is a hands anatomy fixer that unlike other negative prompts will not alter the overall characteristics of your character. Remember to wrap the trigger inside a negative prompt like this: <negative-hands:-2> view gallery on web: https://debug.graydient.ai/concept/negative-hands model family: SD15 example: https://www.graydient.ai/wp-content/uploads/2023/07/hands.jpg more info: https://civitai.com/models/56519/negativehand-negative-embedding

- (13.09.2023 08:36:31 UTC+02:00) <bad-prompt> ( inversion ) by frequent-flyer token: bad\_prompt\_version2 from https://civitai.com/models/55700/badprompt-negative-embedding to use: /render <bad-prompt> playing on a sunny day tags: -negatives description: Bad Prompt negative embedding by Nerfgun3 is a general detail booster, which can fix details like hands. To use it, put it in your negative prompt with a negative weight like: [<bad-prompt:-1>] view gallery on web: https://debug.graydient.ai/concept/bad-prompt model family: SD15 example: https://www.graydient.ai/wp-content/uploads/2023/07/bad-prompt.jpg more info: https://civitai.com/models/55700/badprompt-negative-embedding

- (28.09.2023 05:09:18 UTC+02:00) I see, so the length of the message is cut so the models at the end of the prompt can't be seen, and they're not itemized either, because the message length

- (17.01.2024 09:56:49 UTC+02:00) hello and welcome! here's a quick way to do it 1. click on @piratediffusion_bot 2. type /webui 3. add /dashboard/ to the URL 4. click on API key

- (22.01.2024 17:10:07 UTC+02:00) Welcome! Please give our software a spin, it's quite the rabbit hole. Our software suite comes with Telegram, Web render / inpaint / upscale, Model Training, Cloud Storage, and a chat bot called Polly GPT Please check out our website: https://graydient.ai

- (27.01.2024 06:46:19 UTC+02:00) I'll setup 4 so we can test the Stability vae was removed. If you want to use it again, add this to your prompt: /vae : GraydientPlatformAPI\_\_sd-vae-ft-ema

- (20.02.2024 15:20:06 UTC+02:00) This is a support channel for the Graydient API - https://app.graydient.ai/api-help/ We can't assist with the scraping of websites, this is a generative platform for AI images and chat bots

- (20.02.2024 18:43:11 UTC+02:00) sure, can you tell us more about your workflow? what does a day of activity look like, is it just for personal use or for a discord bot, or something else?

- (23.02.2024 02:28:16 UTC+02:00) we have a fix coming for webui that remembers the last prompt. short term it's available by clicking the history button

- (24.02.2024 07:04:07 UTC+02:00) API Docs: https://app.graydient.ai/api-help/

- (31.03.2024 02:30:07 UTC+02:00) you should be able to add it to your prompt right from the webui concepts system

- (29.04.2024 01:10:12 UTC+02:00) Can you tell us more? So for example, are you wanting to enter one prompt, and see the image change over and over every few seconds on the screen, like a screen saver?

- (29.04.2024 05:35:01 UTC+02:00) Try a prompt like this /render /guidance :2 /sampler :dpm2m /karras /size :1024x1024 /nofix ((high quality, masterpiece, masterwork, cinematic)) Insert your prompt here <realvis4light-xl> /steps :6 /images :9 /karras <simplepositive-xl:0.2><detail-tweaker-xl:0.2> film grain [[<<neg-eyebleach3-xl:-2>]] [[<fastnegative-xl:-1>]] [[low resolution, worst quality, blurry, mediocre, bad art, deformed, disfigured, elongated, disproportionate, anatomically incorrect, abstract]]

- (08.07.2024 11:51:55 UTC+02:00) To generate a token you can access it by @piratediffusion_bot Type /webui Then in the dashboard url in your test subdomain dashboard url add /token/

- (19.07.2024 16:23:54 UTC+02:00) @tlack305 @Hassanrsiddiqi if someone's available, Jonathan needs an API key that can access his private loras (or) a change in the database to move a lora to a global scope He's not able to generate his own key and is using one created by me in the meantime

- (19.07.2024 16:26:41 UTC+02:00) Jonathan as a short term fix, if you're in a hurry, you can login to https://my.graydient.ai/catalog and rebuild the lora there by uploading the pictures, and that can be read by the temp api key or use any of the loras in https://my.graydient.ai/concepts as a placeholder in the meantime

- (04.11.2024 02:52:01 UTC+02:00) yes, it's possible when the full URL path is provided check post parameters here: https://my.graydient.ai/api-help/

- (04.11.2024 03:23:10 UTC+02:00) In a different workflows API I see the variable called a different name, I wonder if this will help:

- (08.11.2024 06:56:52 UTC+02:00) we have a ton of upscalers, try /facelift - does retouch and upscale with realesrg 4x /facelift /photo - same but no retouch /facelift /anime - great for illustrations and paintings too then in workflows there are more /wf /run :upscale-remacri (my current favorite) /wf /run :upscale-4xultrasharp (kim209) /wf /run :upscale-swinir /wf /run :upscale-8k (nkmd) /wf /run :upscale-supir — this is a latent one, uses juggernaut xi. you can guide the prompt and guidance etc, will creatively upscale If we're missing one let me know, I'll add it asap

- (16.11.2024 15:51:14 UTC+02:00) this is the token for the my.graydient.ai dashboard, and your api token will be generated on a different url we give you a full copy of the software on a random subdomain that only you control, for your privacy and security

- (27.11.2024 01:40:43 UTC+02:00) Heres a workflow example $ cat create-render-workflow.sh TOKEN= cat token-dev.txt curl -v \ http://localhost:26403/api/v3/render \ -X POST \ -H "Content-Type: application/vnd.api+json" \ -H "Accept: application/vnd.api+json" \ -H "Authorization: Bearer $TOKEN " \ -d '{"options":" /workflow /run :basicflow3", "prompt":"ugly guy", "callback_url":" https://femdragon.free.beeceptor.com/render "}'

- (02.12.2024 06:45:20 UTC+02:00) Flux inpainting and outpainting workflows are now available. These are early preview implementations for developers, available right now now on our API. Please check the notes in /workflows for instructions, and example prompts are available in the Play Room channel. The workflow names are: /wf /run : inpaint-flux /wf /run : zoomout-flux

- (08.12.2024 14:07:38 UTC+02:00) repeating the /debug command again in your bot should work or try a dirty prompt in @piratediffusion_bot to make sure the filter is turned off

- (08.12.2024 14:20:44 UTC+02:00) in this example, the funny spelling of Hulk Hogan in this tag set. I am using v's and 0's because later, when I go to render, I need it to that Hulk doesn't mean the green hulk we are working against the biases of what the AI thinks you are prompting for

- (08.12.2024 15:38:15 UTC+02:00) its your first model, right? don't be so hard on yourself, you did great there's a few more things to learn. please check our FAQ on best practices as a possible next step, use our photopea editor to drop all of the photos so that its only the face, and remove any images that look dark or blurry then try the prompt again

- (02.01.2025 00:04:03 UTC+02:00) For plus members, video is now available via api example $ cat create-render-workflow.sh TOKEN= cat token-dev.txt curl -v \ http://localhost:26403/api/v3/render \ -X POST \ -H "Content-Type: application/vnd.api+json" \ -H "Accept: application/vnd.api+json" \ -H "Authorization: Bearer $TOKEN " \ -d '{"options":" /workflow /run :video", "prompt":"cinematic low angle video of a ronald mcdonald clown eating a square hamburger, the restaurant ((sign text says Wendys)), ronald mcdonald's clown costume has red afro hair and a red nose with white face paint, the restaurant is brown, the burger is pointy and square, the background has blur bokeh and people are walking around", "callback_url":" https://femdragon.free.beeceptor.com/render "}'

- (02.01.2025 00:04:22 UTC+02:00) you can also do img2vid with the animate workflow

- (02.01.2025 11:32:48 UTC+02:00) The video generation is working great for the most part; however it seems about 10-20% of requests just get stuck forever and never finish; do you know anything about this issue? Example: https://my.graydient.ai/api/v3/render/ke1j6A

- (20.01.2025 02:34:34 UTC+02:00) It is possible to purchase multiple API keys for your ideal number of lanes right now but we also offer a dedicated server solution where your workflow is always on and can be set up to your specifications of course, Tlack's point, these options aren't priced for personal use let us know more about your project, we can put together an estimate for you

- (30.01.2025 05:12:18 UTC+02:00) This is now active, but API isn't available for Pro plans. Would you like to upgrade to Plus? It also features 12 LLMs and Video Generation. It's a price difference of $20

- (15.02.2025 17:17:28 UTC+02:00) Do you have the basic render down? You can add render parameters as shown here: https://piratediffusion.com

- (15.02.2025 17:19:47 UTC+02:00) curl -v \ https://app.graydient.ai/api/v3/render \ -X POST \ -H "Content-Type: application/vnd.api+json" \ -H "Accept: application/vnd.api+json" \ -H "Authorization: Bearer YOUR_TOKEN " \ -d '{ "prompt":"an elephant wearing a hat /images :1 /seed :2343234 /guidance :5 /sampler :ddim", "callback_url": " https://mydev.ngrok.io/webhook/render " }'

- (16.02.2025 02:09:06 UTC+02:00) This implementation supports these samplers: /sampler:ddim /sampler:dpm2m /sampler:heun /sampler:k_euler_a /sampler:k_euler /sampler:upms /sampler:lcm /sampler:lcm_base Use /render /sampler:k_euler_a cute kitten to change sampler for render Best sampler is a matter of personal preference

- (16.02.2025 02:10:53 UTC+02:00) you're close but that sampler isn't supported by diffusers graydient supports two separate render engines, diffusers and comfyui to use a comfyui sampler or scheduler, please create a workflow first that is also the way to do latent upscaling in a single api command I can send you a mapped template for sdxl / illustrious with built in upscaling

- (16.02.2025 02:12:32 UTC+02:00) a good example of this is the flux workflow. /slot8 :1.4 is mapped to an upscale factor so its a single api call that can control the upscale but it is doing multiple steps within the workflow. we don't support multiple chains like that at the command line at this time its either render or upscale (or) workflow with many steps

- (05.05.2025 16:51:38 UTC+02:00) are you looking for the api integration docs? https://cloud.graydient.ai/api-help/

- (23.05.2025 04:18:59 UTC+02:00) Welcome to Audio/Video Plus! Your account is now activated, though may take a few more minutes to sync to all servers. In addition to video and audio generation, you have also unlocked every LLM that we host. You can choose these when you create your own chat bot. Audio generation: https://t.me/+tg0VhWL-JhBlOTg5 example: /wf /run :music-ace [verse] gonna make some songs [bridge] gonna make em [chorus] with pirate diffusion yeah! /slot1 :oldies jazz Video generation: https://graydient.ai/generate-unlimited-ai-videos-with-graydient-now-available/ There are various workflows video from 4 different AI models: LTX, HunYuan, SkyReels and the latest: Wan 2.1. The best resolution for video starts at 320x320 and a sweet spot for social media is 512x640 or 640x280 There are two classes of video workflows. The "animate" workflows require an image input. The "video" workflows are text-to-video. The Q number is the quality of the model. Lower quality models produce longer videos, whereas Q8 is the best available. Videos take a maximum of 3 minutes to render. If you waited longer than 3 minutes, try lowering the settings or removing special characters or extra spaces from your prompt. If it's stuck, type /cancel . Also new! WAN lora mini video models are here, for things like poses and special effects. Use them with the special wan workflows named 'lora'. Hundreds of WAN loras will be available shortly. Here's how to use the video commands with Telegram: https://graydient.ai/pirate-diffusion-guide/#videos While that's propagating, please check out how to prompt for video in our PlayRoom Channel. It takes some practice, please check the examples in Playroom for things like how many steps and what resolutions work best. Each model has its own quirks. https://t.me/+KD-269gIRqFhOTNh To use the new Image-to-Video feature, right click on a photo with the command /wf /run :animate-wan21 and your prompt There are examples in the channel above ^ It's a great place to get ideas for prompts and explore all of the features of the bot. And for NSFW videos: https://t.me/+UD598F41hBgzNmNh Feel free to make videos in these channels. To make videos privately, click on @piratediffusion_bot You'll also find the Map of PirateDiffusion there, for interest groups like anime, digital art, and more. Have fun!

- (30.05.2025 04:19:34 UTC+02:00) try pointing a web-enabled llm at this to help you vibe it https://cloud.graydient.ai/api-help/

- (21.06.2025 05:53:14 UTC+02:00) its unlimited, we dropped all token pricing

- (18.08.2025 16:09:26 UTC+02:00) here you go: https://cloud.graydient.ai/api-help/ the pattern you're looking for is workflow following command for example, these are popular workflows for video right now: video-wan22 = text to video and animate-wan22 = image to video

- (17.10.2025 10:52:10 UTC+02:00) try this: https://cloud.graydient.ai/api-help/#chat

- (04.11.2025 07:28:41 UTC+02:00) you are specifying a placeholders array right? If so, do /faceswap /source:IMG1 (if IMG1 is in the array) and init_image here's an example using curl $ cat create-render-faceswap.sh TOKEN="Sb6iTpGXMnk6O3NVdZOSns7-LHhusJ-D9-twvgbwCAwn_0ef" curl -v \ http://localhost:26403/api/v3/render \ -X POST \ -H "Content-Type: application/vnd.api+json" \ -H "Accept: application/vnd.api+json" \ -H "Authorization: Bearer $TOKEN" \ -d '{"num_images":3, "prompt":"/faceswap /source:URL1", "callback_url":"http://mockbin.org/bin/9f9ef127-1194-43fd-9a20-57c82758438f", "init_image":"https://piratediffusion1.s3.amazonaws.com/renders2/JyjK3W/00001-r-pro-sl-i8i55.jpg", "placeholders":{"URL1":"https://piratediffusion1.s3.amazonaws.com/renders2/JyjK3W/00002-r-pro-sl-i8i55.jpg"}} '

- (04.11.2025 07:29:02 UTC+02:00) Added this bit about calling a workflow with an example https://cached.graydient.ai/api-help/#render

- (04.11.2025 15:04:09 UTC+02:00) is there a workflow called flux-ur4? try that first directly from your @piratediffusion_bot like /workflow /run :flux-ur4 test if that does work, try it like this curl -v \ https://cached.graydient.ai/api/v3/render \ -X POST \ -H "Content-Type: application/vnd.api+json" \ -H "Accept: application/vnd.api+json" \ -H "Authorization: Bearer YOUR_TOKEN " \ -d '{ "init_image": " https://piratediffusion1.s3.amazonaws.com/renders2/Ve53eN/Ve53eN-workflow2421v4-0-ZH82NHLV3.png ", "prompt":" /workflow /run :edit-qwen Change her hair from green to red", "callback_url": " https://mydev.ngrok.io/webhook/render " }'

- (05.11.2025 01:54:18 UTC+02:00) It seems that workflow is down in general, it doesn't work from bot responses either I will try to contact the creator who made it or unpublish it Please try a different one in the meantime

- (05.11.2025 03:09:34 UTC+02:00) it seems related to how the lora is hosted or linked in the workflow nWill assume non-transactional DDL.\nNo target revision found.\nStarting server\n\nTo see the GUI go to: http://0.0.0.0:4061 \ngot prompt\nFailed to validate prompt for output 55:\n* CombinedDiffusersLoader 42:\n - Value not in list: sub_directory: 'duelanimax' not in (list of length 81)\n* LoraLoader 59:\n - Value not in list: lora_name: 'ChelPony_586648.safetensors' not in (list of length 810)\nOutput will be ignored\ninvalid prompt: {'type': 'prompt_outputs_failed_validation', 'message': 'Prompt outputs failed validation', 'details': '', 'extra_info': {}}\n",

- (06.11.2025 15:11:04 UTC+02:00) I know you're posting this as an example, but are you putting in your webhook url? make sure we can reach that (check your ports, etc)

- (06.11.2025 15:18:26 UTC+02:00) replacing this placeholder, I mean: https://your-webhook-url.com/webhook

- (14.01.2026 15:39:41 UTC+02:00) API docs in more languages! (WIP) https://beta.graydient.ai/graydient/en/api/v3 Please explore this work-in-progress guide and let us know how we can improve it What's vague, hard, or confusing? Please let us know

- (07.02.2026 08:36:45 UTC+02:00) yes there's a few video faceswap workflows like wanimate-face wanimate-puppet look into the video-to-video section of the workflows for them

- (07.02.2026 08:38:34 UTC+02:00) /workflow /run:hamtest /size:640x448 /seed:597 cinematic movie clip of Hagrid singing Scottish folk songs at murky pub. His messy hair and beard is swinging in his passionate performance. <ic-detailer-ltx2> /xray (time: 252s, debug ID: RKYlnx6 - Im5bJBe )

- (07.02.2026 08:40:11 UTC+02:00) that's the debug output but you can use a controlnet preset like for example reply to an image in your chat with /control /new : billy so we can now use that short name in our video faceswap then upload your target video and reply to it with: /wf /run :wanimate-face /image1 : billy and that's all you have to do.

- (13.03.2026 12:33:53 UTC+02:00) I think you're looking for this: Note that over the API, you may need to use the placeholders parameter in order to get the image1 parameter to work correctly init_image (and/or init_video) is the equivalent of "replying" on Telegram, then placeholders are like using /control /new :...

- (27.03.2026 09:02:27 UTC+02:00) Sure, to what degree? If you mean to distribute to everyone, you can DM it to me and I'll get it done. I just need a photo and some instructions on how to use it, tokens, triggers, etc If you mean to use it privately, sign up for a Pro or Plus (for video and for API) account on https://graydient.ai then after you activate your bot click @piratediffusion_bot type /concepts /edit add the huggingface safetensors file and you're off to the races. That will be privacy scoped to your API key, Telegram bot, and the web UI that is paired with your bot, so if you're already logged into an account, log out of it and get in with the /concepts /edit command

- (27.04.2026 02:42:02 UTC+02:00) For personal use, the Plus plan has API. The business plan is for building apps and launching reseller websites. Click @piratediffusion_bot and type /api to get started

- (27.04.2026 11:13:22 UTC+02:00) /workflow /run:animate-ltx23 /size:640x640 /seed:828256 the woman is promoting a product in her hands. she says "Hey API developers, I'm here to sell you this soap! It cures cancer and diabetes. Drink some today!" and then she winks and smiles and there is a pause. Her face and hands are very expressive in the style of user generated tik tok influencer videos /length:181 (time: 149s, debug ID: RBZrgJ4 - IlZKONY )

- (06.07.2026 10:00:42 UTC+02:00) Yami try the workflow with base settings over telegram like /wf /run :watever hello world and see if it renders. of course some need fresh input images or videos, etc if that still doesn't render, please post the error code like xxxxx-xxxx


## Russ (46 messages)

- (21.06.2025 17:04:18 UTC+02:00) For what its worth, I do think that would be your best bet - use the personal/pro API to design your application and continue iterating/working on it until you're confident that its at a stage for you to do a release in which you'd then move to a business plan Also you might already know this one, however since you noted making an Android app, you'll definitely want to ensure/plan for your app talks to some server that makes the request for the user, rather than talking to the Graydient API directly from the device as you'll want the server to have the API key rather than your app itself - you'd pretty much need that anyways because of how the callback system works (the API expects you to provide a webhook URL to communicate results back to) but thought it'd be good to note just in case 😅

- (21.06.2025 17:24:45 UTC+02:00) Well in theory the other way to do it would be to write a fake implementation of the API using the example responses - but I've never been a fan of that approach because the subtleties of what happens in live vs documented on any API will always be present But I do think your idea is pretty cool! I do enjoy how flexible the API is, so I'd say it would work well with your goals 😁

- (24.07.2025 04:49:41 UTC+02:00) Try /conceptbrowser in a DM, that will make an auto login link to your community, then on the navigation header click your username and there should be an API tokens option

- (24.07.2025 05:03:54 UTC+02:00) Seems like your account will need some manual intervention then as it should be up next to the render archive button area

- (02.09.2025 22:55:59 UTC+02:00) You'll want to make sure init_image is a link to the initial image you want the animation to be based off of, make sure its a publicly accessible URL and a direct one too (can't link to a HTML page that has the image embedded on it, for example)

- (08.10.2025 11:24:34 UTC+02:00) Do you have any questions about the API?

- (24.10.2025 15:17:39 UTC+02:00) There's an undocumented parameter on the Render endpoint called error_url which works pretty much the same as the regular callback_url except that it'll be sent upon an error occurring, and you'll get some JSON that looks a bit like this https://pastebin.com/rSsCjrCc In my case I use separate endpoints but of course you can just use the same URL if that works better for you (Every now and then the error hook still won't fire, but I just consider any requests that don't come back in 5 minutes to be "failed", as I believe on the Graydient side jobs can't exceed ~3 minutes anyways - so the combination of these two pretty much covers it well enough)

- (06.11.2025 19:27:30 UTC+02:00) Is this coming from the callback, or is this just the initial response to the POST request? Also, along with your callback_url put an error_url too, that way if there are any issues that come up during the render attempt, you'll get some data with the error message, error code, etc

- (14.01.2026 23:55:35 UTC+02:00) Oh boy, its time for another one of these long messages that I'm famous for... brace for impact! [For what its worth, I did actually trim this down a little bit from the original version lol] API response examples would be worth adding (then truncate any list style responses, adding an example of the entire concepts endpoint would overload the page heh) - this was something I remember initially struggling with, as some of the expected response structures ("shapes") were noted but then seemed a bit different from the live responses For example, the "render completed" webhook example has two documented fields about estimated times - but this doesn't make a lot of sense, shouldn't this be in the render "submitted" initial response? I don't recall seeing this in an actual payload - but if it actually is in the completion hook, why is it an estimate and not the "actual" time? (Hence why I think its supposed to be in the render submit response - but I don't believe it is) These two come to mind specifically because there's not really any sort of way to check progress (or be notified of progress updates, either/or) so an estimate would be nice to show to users; You can try to make your own estimate based off previous runs, but you need a pretty steady flow of requests otherwise that will drift way too much to be worthwhile Speaking of that, someone should add the error_url parameter/webhook payload to the render request parameters - its newish but an important one! Looking into using the KB API soon, but I'm a bit confused on "requires domain ownership" - how do I verify the ownership of a domain or even create one? Or is domain a literal domain name that you're just passing in? It also only has response details of the search endpoint, the others should at the very least get the "description" of what to expect the response structure to look like 😅

- (13.03.2026 20:35:13 UTC+02:00) (On a side note, I'd highly suggest using either the callback-via-webhook or websocket system to get instant notifications on when a request either finishes or fails, that way you don't have to wait on polling which you're not technically supposed to do anyways - it works very nicely! 😁)

- (15.03.2026 23:52:10 UTC+02:00) Hmm, I'm not nearly familiar enough with TG's dev policies to comment directly 😭 However, everything in the PD bot's result message should be available over the API, unless you're listening for stuff generated from "outside" your app maybe? Think I'm a little confused about the root of the use case you're trying to tackle 😅

- (16.03.2026 12:45:49 UTC+02:00) /render doesn't use any workflows (well, usually), it only is used for SD1.5/SDXL based models (which is indeed specified by <model> - not sure which one it uses by default if you don't pick one) So you'd use /workflow /run:workflow-name-here if you wanted to use a workflow

- (16.03.2026 12:59:26 UTC+02:00) That's one of the interesting things about the API, the prompt field basically uses the exact same command format as telegram, so if you generate a render with the bot (regardless of /workflow vs /render ) and copy that command and use it in the API prompt field, that will work exactly the same So the API form of /render /size :... /blah :... Is precisely that 🙂 There are "concepts" which are your full/checkpoint models and LoRAs, but there are also workflows <hentai-cinematic3-xl> sounds like a full model concept, so you'd use it with /render rather than /workflow Like /render /size:768x1024 A woman sitting at a diner table <hentai-cinematic3-xl> in both the PD bot and the API should both run using that model

- (16.03.2026 13:03:53 UTC+02:00) To be fair, I have a whole abstraction layer on top of it too lol, and represent Job requests as proper JSON objects Then on the server side code there's a giant function that then converts it over to a /render or /workflow command (There's also a "raw" toggle that bypasses that and just sends a raw render command without trying to interpret the rest of the object, which has been good for skills)

- (18.03.2026 23:01:23 UTC+02:00) However, if a workflow accepts loras, you can check to see what model families are supported by that lora slot, that's as close as you can do from what I understand

- (18.03.2026 23:06:23 UTC+02:00) I didn't realize the concepts endpoint actually had a search method now lol It's very well possible the search function is a little borked

- (18.03.2026 23:11:06 UTC+02:00) Annnyways, the docs don't list all the family names, it only lists SD15/SDXL/Flux Here's the list that I have ( @SerialName indicates the actual name from the API)

- (20.03.2026 02:02:44 UTC+02:00) Are you already using webhook callbacks for results? If so, add error_url to your initial request, which will get fired whenever an error happens during a render If you're using WebSockets, you can also listen for the error event

- (20.03.2026 20:06:57 UTC+02:00) You'll want to use image1 and image2 in the actual prompt, paired with a placeholders dictionary Each dictionary key must start with URL so in your prompt do /image1:URL1 /image2:URL2 then in the request object add { "placeholders": { "URL1": "https://...", URL2: "https://..." }, "prompt" :...." }

- (20.03.2026 20:09:33 UTC+02:00) As tlack mentioned, you can always try the commands in telegram too, just to verify whether the command is correct As far as I recall, you can pass the urls directly in the prompt too rather than needing to make a control for it

- (20.03.2026 20:15:28 UTC+02:00) The prompt that you're sending to the API _is_ a Telegram command, so you should be able to copy and paste that directly into your conversation with the pirate Diffusion bot to run it

- (22.03.2026 10:44:47 UTC+02:00) There are quite a few other edit workflows that you can use in the mean time though! Such as the Kontext workflow ( kontext-flux ) that Captain mentioned, or any of these

- (28.03.2026 16:56:45 UTC+02:00) Hi, do you mean you need help getting started using the API? Also, I wouldn't recommend posting personal details like your phone number in here, or in spots around the Internet in general 😅

- (08.04.2026 12:48:13 UTC+02:00) You'll also still want init_image , basically init_image is the equivalent to "replying" to an image on Telegram Then the /image1:URL1 + placeholders dictionary is the equivalent of doing /control /new:name as one command (to save a ref image) and /wf /run:... /image1:name The init_image for that workflow will be the target image you want, then image1 is the "reference head" so to speak

- (26.04.2026 17:55:13 UTC+02:00) For personal usage, the API only costs a pro plus plan - unless you're looking for business pricing? As for init_audio I haven't tested it just yet, in theory it should work the same way as init_image and init_video however. Do you have an example of what you're trying to do?

- (26.04.2026 18:14:32 UTC+02:00) I'm not a staff member, so I am not sure what the business pricing is, you'd want to speak to @tlack305 or @aiaiaicaptain for that My general understanding is that if you're using the API for just yourself, then the pro plus plan is all you need, whereas if you plan on having others use it, that's when you need a business plan

- (27.04.2026 07:58:20 UTC+02:00) I'm not familiar with HeyGen unfortunately, so I can't say. But what I can say is that the API is extremely flexible - the BitVector stuff that I run is built entirely off the API (with a very few auxiliary things done outside the API) If you're looking to build anything AI related, you'll have a much easier time trying to use Graydient's backend and infrastructure rather than building out your own

- (27.04.2026 08:17:55 UTC+02:00) I more or less mean that it's going to be easier for you to let them handle purchasing and setting up GPU nodes, then tying it all in, rather than you having to do it yourself (pricey and is a headache, I imagine) BitVector is a discord bot and alternative web client that I made for Graydient customers to use https://wiki.bitvector.app/starter/using-skills All of the rendering, workflows, etc all use their API, I wrote the "coordinator" that talks to the API

- (30.04.2026 04:46:58 UTC+02:00) Try lowering the step count, by default the ernie workflow uses /steps:20 , you could try /steps:10 and see how the quality looks Ernie is a very new model, it's not as optimized as more traditional models are

- (30.04.2026 04:59:32 UTC+02:00) Skills use a global LLM configuration right now, it can't technically be changed on a user / API level at the moment

- (30.04.2026 05:13:55 UTC+02:00) Try running a skill through the API again now

- (30.04.2026 05:59:22 UTC+02:00) Oh hey that's me! (I made the workflow + skill) Glad to hear it, Chroma is quite powerful especially for realism. It can do anime stuff to an extent too, of course it can't do videos since its purely an image generation model, but its quick at the images it can generate

- (30.04.2026 06:04:58 UTC+02:00) For Chroma you'd use /workflow /run:chroma1-flash Prompt here which would indeed be faster without the skill - however at the cost of having no prompt enhancing, it'd just run the user's direct prompt

- (30.04.2026 06:06:43 UTC+02:00) /render => Used to run the older SD15/SDXL models /workflow /run:... => Used to run workflows which encapsulate newer models Neither of those have "auto prompt enhancing", nor setting selections Skills specifically are designed to enhance the prompt *and* pick settings if the skill encodes that. For example, my skills will use /size:768x1280 in the command if the given request sounds like it'd be better for a portrait aspect ratio

- (30.04.2026 06:07:52 UTC+02:00) Prompt enhancing is like lets say someone just types in "A woman in a red dress" and nothing else, that prompt *might* give the user what they're looking for, but a skill will usually expand the prompt as defined by the skill's instructions/examples If you do /skill /show:chroma1-flash in your pirate diffusion bot, it will give you the skill definition file and you can see all the instructions I've put into "How to build a good prompt for Chroma specifically"

- (30.04.2026 06:08:47 UTC+02:00) /skill /run :ernie An isometric render of an RPG castle game map

- (30.04.2026 06:08:47 UTC+02:00) Running skill: ernie Generated command: /wf /run:ernie /size:1024x1024 /guidance:4.0 /steps:20 Isometric top-down 3D render of an RPG castle game map. Centered fortress with stone walls, four corner towers with red cone roofs, central keep with blue banner. Surrounded by moat, wooden bridge, outer village with thatched cottages. Dense forest, winding river, mountain range in background. Grid lines overlay for tactical positioning. Miniature scale, detailed cobblestone textures, tiny figures of knights and adventurers on paths. Warm golden sunlight, soft shadows. Fantasy cartography style, lush green grass, sparkling water. High detail, clean edges, game-asset quality. Explanation: This will generate an isometric RPG castle game map using the ERNIE diffusion model. The prompt describes a detailed fortress with surrounding terrain, grid overlay, and fantasy cartography styling — optimized for the crisp, hyper-detailed output ERNIE excels at. Default settings (20 steps, guidance 4.0) provide a balanced mix of speed and quality. Executing...

- (18.05.2026 21:53:16 UTC+02:00) Smh I should've asked if this existed, I had built my own image request handling myself by sending it to OpenRouter, getting the description back, and then passing that description to the original persona endpoint and handling the description as a bit of an "out of band" element in my app lol

- (18.05.2026 21:56:35 UTC+02:00) Ahhh, see I was a little confused because I thought I'd recalled reading two conflicting pieces of info - one was a message saying that none of the bots accepted images over the API, but then the API docs also say that it should work but only for bots that are using underlying vision models, so I just went with the out-of-band method so that "all" bots could effectively be blessed with vision capabilities from the user's perspective

- (30.06.2026 13:01:49 UTC+02:00) You'd need to create a chat bot persona first, then you can chat with the bot over the API, as it doesn't let you just directly access upstream LLMs raw There's a persona I made named "Ansel" which is made for generating natural language prompts and can do NSFW Feel free to try it over the API or even here in Telegram by using the /Anselbot command (in your DM with Pirate diffusion, won't work here), that way you can get an idea of how that works

- (02.07.2026 04:16:47 UTC+02:00) I just double checked, token is what you want (Note: It'll be an empty string if the lora doesn't have one set)

- (06.07.2026 09:32:52 UTC+02:00) As far as I'm aware it should manage the queue for you - have you tried with really simple requests to verify its not just an issue with say, a workflow actually bugging out?

- (06.07.2026 09:53:45 UTC+02:00) Those don't look like timeouts, I believe that usually has a very specific timed out error Anything that isn't Text-to-Image sometimes has weird invocation patterns, like in some cases a workflow might require init_image , whereas others might require you to use an /image1 parameter combined with the placeholders object

- (13.07.2026 04:24:28 UTC+02:00) DeepSeek should be pretty jailbroken by default over their API actually, I don't think I've ever had it actually reject a NSFW related request It's usually the American Frontier models that you have to jailbreak, which aren't even worth trying to do anymore these days since its such a cat and mouse game lol

- (13.07.2026 17:42:53 UTC+02:00) If you do end up testing it out, certainly let me know how it goes! Kinda feels very much like using ChatGPT/Gemini's "make image/video over chat" thing, and goes to show how incredibly powerful the Graydient API can take you

- (17.07.2026 16:10:24 UTC+02:00) If you have the render hashes then @tlack305 can probably have a look to see what might've occurred I've seen the issue before of no error+no result, but it's been exceedingly rare in my experience and is just covered by a 5 minute watchdog task I have in my system that force fails anything that is stuck (5 minute covers a ~2 min queue time which is rare, plus the 3 minute maximum execution time that renders can take)


## Ape Agent (10 messages)

- (04.08.2025 15:18:50 UTC+02:00) Hi everyone, can someone pls explain how I get access to API token? Thank you!

- (18.08.2025 13:37:13 UTC+02:00) hey everyone. Can you please point me to the right api documentation to create text-to-video and image-to-video. I'm checking here https://my.graydient.ai/api-help/#render is it corect?

- (18.08.2025 16:17:15 UTC+02:00) when using image to video it should be used init_image?

- (29.08.2025 16:39:12 UTC+02:00) this is my request log Submitting Graydient video render request: { url: ' https://app.graydient.ai/api/v3/render ', payload: { prompt: ' /workflow /run :animate-wan22 /size :704x1024 /length :81 /fps :16 she smiles while looking at the camera [[deformed, distorted, disfigured, motion smear, blurry, pixelated, hyper]]', callback_url: ' https://ef8f10943e2a.ngrok-free.app/api/webhook/graydient-video-render?userId=11026&videoId=394 ', init_image: 'my image' }, hasToken: true }

- (29.08.2025 16:40:13 UTC+02:00) but strange I waited like 5 minutes to render

- (02.09.2025 22:58:36 UTC+02:00) What I usually do is generate image with Graydient. Store it in my cloud service. Give graydient the link to it through init_image

- (06.02.2026 14:11:12 UTC+02:00) gey guys. Can someone please tell me where I can find documentation on how to do faceswap?

- (06.02.2026 14:30:09 UTC+02:00) ohh and I see the faceswap is for telegram but how I do it programatically via api?

- (08.04.2026 11:58:35 UTC+02:00) hey guys. I'm looking for an api call where I can send image and change it based on the prompt I'm sending. can you help me here? Thanks!

- (08.04.2026 12:41:49 UTC+02:00) sorry for bothering. What about faceswap?


## Hassan Raza (9 messages)

- (09.09.2023 13:54:48 UTC+02:00) this is the CURL request from my postman. curl --location 'http://localhost:26403/api/v3/render' \ --header 'Content-Type: application/json' \ --header 'Authorization: Bearer TOKEN ‘HERE \ --data '{ "prompt": "a child crawling", "callback_url": "http://www.google.com" }'

- (09.09.2023 13:56:54 UTC+02:00) Here is it in PHP. <?php $curl = curl_init(); curl_setopt_array($curl, array( CURLOPT_URL => 'http://localhost:26403/api/v3/render', CURLOPT_RETURNTRANSFER => true, CURLOPT_ENCODING => '', CURLOPT_MAXREDIRS => 10, CURLOPT_TIMEOUT => 0, CURLOPT_FOLLOWLOCATION => true, CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_1_1, CURLOPT_CUSTOMREQUEST => 'POST', CURLOPT_POSTFIELDS =>'{ "prompt": "a child crawling", "callback_url": "http://www.google.com" }', CURLOPT_HTTPHEADER => array( 'Content-Type: application/json', 'Authorization: Bearer TOKEN HERE ), )); $response = curl_exec($curl); curl_close($curl); echo $response;

- (11.09.2023 11:19:34 UTC+02:00) https://app.graydient.ai/api/v3/concepts/ Try this one.

- (02.11.2023 08:44:30 UTC+02:00) Hi Praeep, You need to provide your image as an init_image param, and in prompt you can write your prompt. Here is the link for docs. https://app.graydient.ai/api-help/

- (02.11.2023 08:49:01 UTC+02:00) You need to signup, to get token. https://graydientplatform.com/pricing-stable-diffusion-api/

- (25.12.2023 17:00:46 UTC+02:00) You need to signup from web, to get the API key.

- (18.01.2024 14:39:34 UTC+02:00) callback_url: NGROK ADDRESS in request body.

- (25.01.2024 14:53:59 UTC+02:00) You don't need to call API a second time, since you provided the callback url, now the API will call this with the data in body.

- (25.01.2024 15:05:53 UTC+02:00) render_hash endpoint is supported, but Its only accessible when your requests has finished rendering, in this case, you are trying to access the endpoints details right after sending the requests, So there is nothing to share back. Usually a requests gets completed in a ~ minute (but depends on current taffic, image dimensions, prompt and other factors) If you try calling the render_hash API after few minuts, you will receive a response.


## KV (13 messages)

- (08.07.2024 11:39:04 UTC+02:00) I just signed up for a trial, can I please have access to the API token? I want to check the integration with my systems. https://app.graydient.ai/dashboard/token/

- (08.07.2024 12:09:03 UTC+02:00) If possible, can I please DM one of you to get the token?

- (08.07.2024 20:10:14 UTC+02:00) I couldn't find it in the API docs. Anything that I am missing?

- (08.07.2024 20:10:43 UTC+02:00) These options are available on the UI. Hoping I can use them through the API as well.

- (08.07.2024 20:11:56 UTC+02:00) Ah. So you mean, I can use the same prompt as the one on the UI and it will take care of those things?

- (08.07.2024 20:13:50 UTC+02:00) If you guys have an opensource project, feel free to ping me. I can contribute to that as a token of gratitude when I have some time in the future.

- (08.07.2024 20:15:41 UTC+02:00) What is the expectation from the webhook?

- (08.07.2024 20:16:14 UTC+02:00) I could see many repeated requests on my endpoint, even after I responded with status code 200.

- (08.07.2024 20:16:35 UTC+02:00) Also, what about retries? Are there any on your side, once when my webhook is exhausted or lets say unavailable?

- (08.07.2024 20:16:58 UTC+02:00) In the future, I am thinking of having a queue infront of the webhook, but was just curious how you guys have handled it on your end at the moment.

- (08.07.2024 20:19:52 UTC+02:00) retries could be a good to have feature at your end. Just saying. Not every endpoint will remain available all the time.

- (08.07.2024 20:21:23 UTC+02:00) I just noticed that even after returning a 200 status code from by webhook API, I am still getting repeated requests

- (19.07.2024 17:09:15 UTC+02:00) Also, is there any documentation around upscaling images over the API? Please share a reference for the same. TIA.


## P. (18 messages)

- (02.09.2025 22:53:29 UTC+02:00) Im also try to do an api vidéo request for a workflow animate-wan22 , like Mr s below Im little confuse how to référence the image .. On his précédente pose he reference it as Init_image: 'my image' ..😕 How it should be référenced

- (02.09.2025 23:20:31 UTC+02:00) Thr api call work well . Im just struggle with thr callback to get the video back. I receive only the init image . Im searching the good parameter containing the URI of the video generated to download . But I can see on my graydient render space ,it well generated

- (04.10.2025 03:34:12 UTC+02:00) But I feel like the wanimate-replace always render a nsfw whatever input is. Am I right ? Maybe a service restriction or there is a way to force nsfw with an option ?

- (20.03.2026 01:56:11 UTC+02:00) Hello, I would like to understand how to increase reliability with my call to graydient API and make my "working render" rate better. Actually , depending the day my render rate is in a range from 75% to 90% on good day Actually it doesnt "fail", it just I have no callback from graydient for some request even after the estimation time +++ When I call the API render with the render hash to get some information, I just see that "has_been_rendered": false, also "error_callback": null, I suppose there was an error during the workflow process in the graydient error ... Or maybe just a kind of timeout can occur sometime depending of the aleat charge of graydient server ? Dont know if there is there a way to obtain the error when that is happen ? actually im thinking about implement the following process: if no callback occur after 10 minut, automatically do request again . and mayby handling a 6 max time retry Do you also have this kind of problematic ?

- (20.03.2026 13:15:50 UTC+02:00) Thank you ! The error_url working great for me, and make the UX experience better :) Also it help me adjusting the workflow parameter for some which failed often and increase success rate. So today i was trying adding a worflow : I did try add wanimate-face and wanimate-puppet .. but for now i cant make them work trough the API, ( always get some details=unhandled error occurred ) i wonder if could be a parameter input problem. Actually i send init_video for my reference video image1 for my reference image Is it correct ? Do i need to use some of slotx input ? Thank you for your help

- (20.03.2026 19:52:26 UTC+02:00) I also try the blend2-flux2 workflow giving input image1 and image2 but same , having details=unhandled error occurred. does it the correct input to use ?

- (20.03.2026 20:02:24 UTC+02:00) Sure, exemple for wanimate-puppet "image1": " https://sawadeeka.net/gallerie/upload/admin/images/gYN6ne-workflow815v22-1-ZW3GL8HJN.png ", "init_video": " https://sawadeeka.net/gallerie/upload/admin/videos/delete-me.mp4 ", "progressive_return": false, "prompt": " /workflow /run :wanimate-puppet /steps :5 /seed :47410375 a pinay woman is dancing in front of a wall.", and for the blend2-flux2 "image1": " https://sawadeeka.net/gallerie/upload/pilou/images/OG9oPV-workflow2504v34-1-ZT3LSG2SF.png ", "image2": " https://sawadeeka.net/gallerie/upload/pilou/images/d6mpYP-workflow815v22-1-Z6HCZ0ZZ3.png ", "progressive_return": false, "prompt": " /workflow /run :blend2-flux2 /lpw /size :1024x1480 /seed :2226904868\nCreate a new photograph of two persons. Jake from image 1 is sitting on chair. Jake is reading a book. Elle from image 2 is standing behind him. Elle is holding a coffee mug.",

- (22.03.2026 10:41:35 UTC+02:00) But i got a new problem :( Since about 10h ago my workflow edit-flux2 return unknow and look be same here on telegram

- (27.03.2026 17:29:08 UTC+02:00) hello I try using /describe to caption an uploded image It work well on TG but via API .. it dont work

- (27.03.2026 17:42:12 UTC+02:00) Something like that ? /llm <qwen3-235b> describe the image and propose me a prompt ? Or there is a VL? Event it not work on tg i can try start implement on api ?

- (27.03.2026 17:58:50 UTC+02:00) Its also same about bot personna ? I mean are they available trought api ? My goal was just to caption an upload image.. I dont know if there is a way i can achive it now with a availavle workflow or anything. Otherwise ok i will wait it can be available trough api .

- (09.05.2026 20:03:31 UTC+02:00) Ok. Can yiu advise some to me ? I try combiné 3 images I found several workflow , for example blend3-fire but the result is not what I expected : i want combine 3 human portrait in a new cohérent picture like a family photography . As the result I can have a cohérent intégration of the 3 images but problème is the identity are diluated , first will be acceptable but two other two much différent I also try 2 other wf like -pose2people and deepfake-z but they take 2 people maximum, i tried 3 but the third image is not used That why I though could use faceswap 3 time to solve my problem I m open to any solution

- (09.05.2026 20:08:03 UTC+02:00) Ok 👌 i will try continu with those guideness to make a better prompt. Thank you

- (16.05.2026 11:54:51 UTC+02:00) Question about how send the prompt and négative : What is the recommanded way ? Everything in the prompt field OR there is a specific fields mapped to negative field ? If one single prompt field : using bracket to [ put my negatives inside ] or just natural language starting with negative: OR using negative term in prompt like no light no porn ?

- (16.05.2026 12:15:01 UTC+02:00) Ok that seems clear thank you. Same for /render and sd/sdxl ?

- (18.05.2026 21:39:22 UTC+02:00) Hello, I try to use the function chat documented here: API Help curl -v https://myownsubdomain.graydient.ai/api/v3/chat -X POST -H "Content-Type: application/vnd.api+json" -H "Accept: application/vnd.api+json" -H "Authorization: Bearer xxxxxxxxxxxxxxx" -d '{ "persona": "polly", "prompt": "What do you see in this image? Describe it in detail and provide a concise reusable image prompt.", "image_url": "https://sawadeeka.net/gallerie/upload/admin/images/xxxxxxxx.png", "session_id": "admin", "callback_url": "https://sawadeeka.net/gallerie/callback.php?sig=xxxxxx&job=xxxxxxxxxx&slot=0&upload=1" }' I got an answer like this {"data":[{"attributes":{"api_request_data":{"callback_url":"https://sawadeeka.net/gallerie/callback.php?sig=xxxxxx&job=xxxxxxxxxx&slot=0&upload=1","session_id":"admin","sync":false},"id":517620,"persona":{"greeting":"<b>Ahoy! I'm Polly.</b> I can tell jokes, write prompts, and create images. For more advanced image controls, login to My.Graydient and click Tools. <BR><BR><b>Did you know?</b> You can change my personality, my image-making art style, turn off jokes, and give me different abilities like emotes and hashtags. <a href=\"https://graydient.ai/pollygpt-guide/\">Learn how</a> <BR><BR> ","id":"A7BWX1","name":"Polly","personality_summary":"Playful, cheeky, tech-savvy squawk!"},"prompt":"What do you see in this image? Describe it in detail and provide a concise reusable image prompt.","reply_to_response_id":null,"response_id":null,"response_parts":null,"response_text":null},"id":"517620","type":"chat"}],"jsonapi":{"version":"1.0"}} my callback url is never called. Do i make something wrong ? What is the way to troobleshoot ?

- (19.05.2026 17:14:58 UTC+02:00) By the way.. Is there any api available in order to generate a prompt : It would accept as input the humain idea or description and would give as an answer an optimized prompt ? ( and if it can handle any prompt SFW or NSFW , it would be perfect ! ) Actually there is such command available on TG, but i have no idea how to do with API.

- (15.07.2026 22:16:56 UTC+02:00) Hello, I was away for a while like 1 month and today was in the mood to make some picture. Unfortunatly all my i2i request failed. In the meantime my t2i prompt still working First i was thinking maybe the workflow i used was depreciated/deleted but it seem it's all i2i requests which return me same error As an exemple : { "callback_url": "https://mycallbackurl", "error_url": "https://myerrcallbackurl", "prompt": "/wf /run:edit-krea /guidance:8.0 /lpw /images:1 /sampler:dpm2m /strength:0.50 /size:512x512 /steps:28 /seed:6543693524\nmy prompt.", "progressive_return": false, "request_data": { "silent": true }, "session_id": "myuser", "init_image": "https://myimagejpg" } {"errors":[{"status":403,"title":"small mistake in your prompt. unknown `/run:edit-krea`"}],"jsonapi":{"version":"1.0"}} i also tried with workflow word { "callback_url": "https://mycallbackurl", "error_url": "https://myerrcallbackurl", "prompt": "/workflow /run:edit-krea /guidance:8.0 /lpw /images:1 /sampler:dpm2m /strength:0.50 /size:512x512 /steps:28 /seed:6543693524\nmy prompt.", "progressive_return": false, "request_data": { "silent": true }, "session_id": "myuser", "init_image": "https://myimagejpg" } {"errors":[{"status":403,"title":"small mistake in your prompt. unknown `/run:edit-krea`"}],"jsonapi":{"version":"1.0"}} Only différence with my t2i requests are the init_image part. Do you know if there was some changes regarding the API ?


## V (10 messages)

- (12.06.2024 00:40:13 UTC+02:00) Hello, goodnight. I wanted to know if there is a possibility of generating an image via the API already passing the Hires.fix parameters? (Steps, Strength, Scale)

- (08.07.2024 23:19:31 UTC+02:00) They don't display anything in the webhook, and when I go to the endpoint to check the hash, it only displays that "has_been_rendered" is false

- (04.11.2024 02:49:29 UTC+02:00) Guys, there is a way to use external URL images in "init_image" via API?

- (04.11.2024 22:15:35 UTC+02:00) Oh, that was just a test that Captain and I were trying yesterday. The same problem occurs with the URL not being encoded and with the "init_image" parameter. I'll send the response with the changed values, just a moment.

- (05.01.2025 23:12:31 UTC+02:00) I wanted to ask you something. I'm trying to create a workflow for img2img, but I'm having some difficulties. I'm getting this error. Which field should I link to the "Load Image" node? And should I link it to "image" or "upload"? I'm testing it on the web.

- (04.11.2025 16:06:34 UTC+02:00) I have a workflow here that allows passing any SDXL checkpoint for image generation (alternate_sdxl_lora) and several models give an error, giving the following error:

- (04.11.2025 16:10:35 UTC+02:00) Can see in this log: https://cloud.graydient.ai/monitor/workflow/AE958E/v1q10D

- (05.11.2025 03:00:56 UTC+02:00) Is a old workflow, and i’m trying to understand why some checkpoints works and some gives this error

- (05.11.2025 03:11:53 UTC+02:00) Yes, in this workflow I used a workaround to make a LoRA request mandatory; otherwise, it would return an error.

- (13.12.2025 17:55:52 UTC+02:00) I'm having a few small issues with the return of results from the webhook requests. It has been quite unstable for a few days, with some returning and others not.


## J (16 messages)

- (09.09.2023 12:08:32 UTC+02:00) Hi, I got problem to login to dashboard to get API token

- (11.09.2023 11:14:27 UTC+02:00) The API to get concept list is error 404 ( https://app.graydient.ai/api/v3/concept/ )

- (11.09.2023 11:21:21 UTC+02:00) It works, thanks. You may need to fix the API manual.

- (11.09.2023 12:21:06 UTC+02:00) May I suggest you guys to add "nsfw" field to the concept attribute in the API. It will help app developer to do easier filter.

- (11.09.2023 12:25:10 UTC+02:00) FYI, the field "example_url" which mentioned in the API manual does not appear in the actual API response.

- (11.09.2023 17:06:57 UTC+02:00) could you point me the the document for init_image?

- (13.09.2023 05:57:59 UTC+02:00) /render Create a lively, Ghibli - style character with a fluffy appearance and a mischievous expression. Show them engaged in a playful action. Use vibrant colors and a transparent background. <cute-animals-xl>

- (13.09.2023 07:57:22 UTC+02:00) May I suggest to add recipes list to the API?

- (13.09.2023 08:09:23 UTC+02:00) I need you guys help. Sorry if not proper to ask here but I'm struct with this for long time. I'm programmer and not familier with prompt engineering. I would like to create a nice t-shirt design that shown on this civitai model https://civitai.com/models/125267/t-shirt-designs-vector-style-stckers-pod Due to the model is also provided by Graydient.ai , So, I tried to reproduce these example image using telegram and API but I totally failed. Could you please advice me how to create a good prompt to create something like those examples. Sorry to ask here but I'm very headache to do it.

- (26.09.2023 13:14:57 UTC+02:00) Does API support ControlNet? If so, could you please advise how should we call it.

- (27.09.2023 03:22:47 UTC+02:00) I use this command: /render /tall /sampler :k_euler_a /steps :30 /guidance :10 /clipskip :1 /parser :new 1girl, neutral, windy hair (best quality, masterpiece, highres) (intricate details) (cinematic, crisp) <mysterious4-xl> [black and white, monochrome, grayscale] [lowres, blurry] [plain background, white background, simple background] [signature, watermark, text, logo] [normal quality, bad quality, worst quality] [extra limbs, extra fingers, hands] [muscular, muscly, muscles,abs] /images : It cause error 'unhandled error occured' (in telegram) Could you please point out what did I do wrong? FYI, when I call from API, the unhandled error do not return any thing to API call.

- (27.09.2023 03:34:52 UTC+02:00) It's ok, I can wait. However, it would be good if you add /bg to API, I'm really need it 🙂

- (28.09.2023 02:50:24 UTC+02:00) When I create /bg and got mask. Can I reverse mask and use with outpainting in API ?

- (29.09.2023 02:24:33 UTC+02:00) How can I check my API usage (request count)? I will go to production my app soon. So, have to calculate cost.

- (29.09.2023 03:21:40 UTC+02:00) May I request features for telegram. As we discuss yesterday about /showprompt not show model if prompt was too long. Why not you add info to JPEG EXIV data? This will easier to manage, I think

- (02.10.2023 03:26:09 UTC+02:00) Some minor (bug) report: In concept list, there's model with 'model_family' is None. {'concept_hash': 'EpnnO7', 'description': None, 'example_url': ' https://www.graydient.ai/wp-content/uploads/2023/09/blue-pencil03.jpg ', 'info_url': ' https://civitai.com/models/119012?modelVersionId=157560 ', 'is_nsfw': False, 'model_family': None, 'name': 'bluepencil03-xl', 'tags': [], 'token': '', 'type': 'full_model'}


## Red (5 messages)

- (14.12.2024 16:31:01 UTC+02:00) Processing prompt 1/1: /workflow /run :flux-dev /size :1024x1024 /steps :30 A vintage-inspired tshirt design featuring the text "Baltimore" and "Charm City" on a solid chroma key green background. Error submitting prompt: 400 Client Error: Bad Request for url: https://cloud.graydient.ai/api/v3/render/ Response Text on Error: {"errors":[{"status":400,"title":"Missing required parameters"}],"jsonapi":{"version":"1.0"}} Failed to submit prompt: None

- (14.12.2024 16:34:32 UTC+02:00) import tkinter as tk from tkinter import scrolledtext, messagebox, filedialog, ttk import requests import json import time import pandas as pd import logging import threading import os # Import for path manipulation # Configure logging logging.basicConfig(filename='app.log', level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s') # Replace with your actual Graydient API key API_KEY = "-------------------------------" API_BASE_URL = " https://cloud.graydient.ai/api " SUBMIT_ENDPOINT = API_BASE_URL + "/v3/render/" HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/vnd.api+json"} #change to vnd+api+json # Output directory for images (if you add image saving) OUTPUT_DIR = "output_images" os.makedirs(OUTPUT_DIR, exist_ok=True) def submit_prompt(prompt, model_id="graydient/flux-model", max_tokens=100, lora=None): """Submits a prompt to the Graydient API.""" # Construct the options object as seen in the provided image options = { "prompt": prompt, } payload = { "options": options, "model_id": model_id, "max_tokens": max_tokens, } if lora: payload['LoRA'] = lora try: response = requests.post (SUBMIT_ENDPOINT, headers=HEADERS, json=payload) response.raise_for_status() return response.json() except requests.exceptions.RequestException as e: logging.error(f"Error submitting prompt: {e}") print(f"Error submitting prompt: {e}") if hasattr(response, 'text'): #check to make sure response exists before printing text print("Response Text on Error:", response.text) # print response text for debugging return None def process_prompts(prompts, status_bar, output_text): """Processes a list of prompts.""" results = [] for i, prompt in enumerate(prompts): status_bar.config(text=f"Processing prompt {i+1}/{len(prompts)}: {prompt}") print(f"\nProcessing prompt {i+1}/{len(prompts)}: {prompt}") submission_response = submit_prompt(prompt) if submission_response and 'id' in submission_response: result_id = submission_response['id'] print(f" Prompt submitted with ID: {result_id}") status_bar.config(text=f"Prompt submitted with ID: {result_id}") #check for completion in response, no loop needed if submission_response and 'completion' in submission_response: output = submission_response['completion'] results.append((prompt, output)) print(f" Result: {output}") # Update the GUI with results in main thread root.after(0, lambda: update_output_text(output_text, prompt, output)) status_bar.config(text=f"Result: {output}") # NOTE: Image downloading and saving logic would go HERE in the future else: print("Response does not contain a completion field") else: print(f" Failed to submit prompt: {submission_response}") logging.error(f"Failed to submit prompt: {submission_response}") # Update the GUI with the error in main thread root.after(0, lambda: update_output_text_error(output_text, f"Failed to submit prompt: {submission_response}")) status_bar.config(text=f" Failed to submit prompt: {submission_response}") # Update status bar to let user know the prompts are complete root.after(0, lambda: status_bar.config(text="Finished processing prompts")) return results def update_output_text(output_text, prompt, result): """ Update the output text with result on main thread """ output_text.config(state=tk.NORMAL) # Enable editing of output text output_text.insert(tk.END, f"Prompt: {prompt}\nResult: {result}\n---\n") output_text.config(state=tk.DISABLED) # Disable editing output text

- (14.12.2024 16:34:32 UTC+02:00) def update_output_text_error(output_text, error_text): """ Update the output text with error on main thread """ output_text.config(state=tk.NORMAL) # Enable editing of output text output_text.insert(tk.END, f"Error: {error_text}\n") output_text.config(state=tk.DISABLED) # Disable editing output text def load_prompts_from_excel(filename, prompt_column="prompt"): """Loads prompts from an Excel file.""" try: df = pd.read_excel(filename) prompts = df[prompt_column].tolist() return prompts except FileNotFoundError: print(f"Error: File '{filename}' not found.") logging.error(f"File '{filename}' not found.") messagebox.showerror("Error", f"File '{filename}' not found.") return [] except Exception as e: print(f"Error reading Excel file: {e}") logging.error(f"Error reading Excel file: {e}") messagebox.showerror("Error", f"Error reading Excel file: {e}") return [] def browse_excel_file(prompt_entry): """Opens a file dialog to select an Excel file.""" filename = filedialog.askopenfilename(initialdir=".", title="Select Excel file", filetypes=(("Excel files", "*.xlsx"), ("All files", "*.*"))) if filename: prompts = load_prompts_from_excel(filename) if prompts: prompt_entry.delete(1.0, tk.END) #Clear current prompt prompt_entry.insert(tk.END, "\n".join(prompts)) # Insert multiple prompts with newlines def submit_and_display(prompt_entry, output_text, status_bar): """Handles button click, executes logic, and updates GUI.""" prompts = prompt_entry.get("1.0", tk.END).strip().split("\n") #Split by newlines if prompts: # Disable the button while processing to avoid duplicate requests submit_button.config(state=tk.DISABLED) status_bar.config(text="Processing prompts...") output_text.config(state=tk.NORMAL) # Enable editing of output text output_text.delete(1.0, tk.END) #Clear output output_text.config(state=tk.DISABLED) # Start the processing on a separate thread threading.Thread(target=process_prompts_threaded, args=(prompts, status_bar, output_text)).start() else: messagebox.showerror("Error", "Please enter a prompt.") status_bar.config(text="Please enter a prompt") def process_prompts_threaded(prompts, status_bar, output_text): """Run process_prompts on a separate thread and enable the button""" process_prompts(prompts, status_bar, output_text) # Enable the button after processing is complete on the main thread root.after(0, lambda: submit_button.config(state=tk.NORMAL)) if name == " main ": root = tk.Tk() # Assign the root to the global scope root.title("Flux Prompt App") # Input area prompt_label = tk.Label(root, text="Enter your prompt(s): (one per line)") prompt_label.pack() prompt_entry = scrolledtext.ScrolledText(root, height=10, width=60) prompt_entry.pack() # Button to open excel file browse_button = tk.Button(root, text="Load from Excel", command=lambda: browse_excel_file(prompt_entry)) browse_button.pack() # Submit button submit_button = tk.Button(root, text="Submit Prompt", command=lambda: submit_and_display(prompt_entry, output_text, status_bar)) submit_button.pack() # Output area output_text = scrolledtext.ScrolledText(root, height=10, width=60, state=tk.DISABLED) output_text.pack() # Status bar status_bar = ttk.Label(root, text="") status_bar.pack(side=tk.BOTTOM, fill=tk.X) root.mainloop()

- (16.12.2024 10:12:29 UTC+02:00) import tkinter as tk from tkinter import scrolledtext, messagebox, filedialog, ttk import requests import json import time import pandas as pd import logging import threading import os # Configure logging logging.basicConfig(filename='app.log', level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s') # Replace with your actual Graydient API key API_KEY = "enter your api here" API_BASE_URL = " https://cloud.graydient.ai/api " SUBMIT_ENDPOINT = API_BASE_URL + "/v3/render/" HEADERS = { "Authorization": f"Bearer {API_KEY}", "Content-Type": "application/vnd.api+json", "Accept": "application/vnd.api+json" } # Optional: directory to save any output images or logs if needed OUTPUT_DIR = "output_images" os.makedirs(OUTPUT_DIR, exist_ok=True) def parse_telegram_style_line(line): """ Parse a telegram-style prompt line. Example line: " /workflow /run :flux-dev /size :1024x1024 /steps :30 A vintage-inspired tshirt design..." We'll separate the slash-commands (options) from the actual prompt text. """ parts = line.strip().split() options_parts = [] prompt_parts = [] option_mode = True for part in parts: if part.startswith("/"): # This is an option options_parts.append(part) else: # Once we hit a non-option, this is the prompt text option_mode = False prompt_parts.append(part) options_str = " ".join(options_parts) prompt_str = " ".join(prompt_parts) return options_str, prompt_str def submit_prompt(line): """Submits a single prompt line to the Graydient API in the telegram-style format.""" options_str, prompt_str = parse_telegram_style_line(line) payload = { "options": options_str, "prompt": prompt_str, # If you want a callback_url, include it here, otherwise remove this line "callback_url": " https://femdragon.free.beeceptor.com/render " } try: response = requests.post (SUBMIT_ENDPOINT, headers=HEADERS, json=payload) response.raise_for_status() return response.text except requests.exceptions.RequestException as e: logging.error(f"Error submitting prompt: {e}") if 'response' in locals() and hasattr(response, 'text'): return f"Error: {e}\nResponse Text: {response.text}" else: return f"Error submitting prompt: {e}" def process_prompts(prompts, status_bar, output_text): """Processes a list of prompt lines.""" results = [] status_bar.config(text=f"Processing {len(prompts)} prompt(s)...") for i, prompt_line in enumerate(prompts, start=1): status_bar.config(text=f"Processing prompt {i}/{len(prompts)}") result = submit_prompt(prompt_line) results.append((prompt_line, result)) root.after(0, lambda p=prompt_line, r=result: update_output_text(output_text, p, r)) # Small delay to not overload (optional) time.sleep(0.5) root.after(0, lambda: status_bar.config(text="Finished processing prompts")) return results def update_output_text(output_text, prompt, result): """Update the output text with the result on the main thread.""" output_text.config(state=tk.NORMAL) output_text.insert(tk.END, f"Prompt: {prompt}\nResult: {result}\n---\n") output_text.config(state=tk.DISABLED) def update_output_text_error(output_text, error_text): """Update the output text with an error on the main thread.""" output_text.config(state=tk.NORMAL) output_text.insert(tk.END, f"Error: {error_text}\n") output_text.config(state=tk.DISABLED)

- (16.12.2024 10:12:29 UTC+02:00) def load_prompts_from_excel(filename, prompt_column="prompt"): """Loads prompts from an Excel file.""" try: df = pd.read_excel(filename) prompts = df[prompt_column].dropna().tolist() return prompts except FileNotFoundError: print(f"Error: File '{filename}' not found.") logging.error(f"File '{filename}' not found.") messagebox.showerror("Error", f"File '{filename}' not found.") return [] except Exception as e: print(f"Error reading Excel file: {e}") logging.error(f"Error reading Excel file: {e}") messagebox.showerror("Error", f"Error reading Excel file: {e}") return [] def browse_excel_file(prompt_entry): """Opens a file dialog to select an Excel file and loads the prompts into the prompt_entry.""" filename = filedialog.askopenfilename(initialdir=".", title="Select Excel file", filetypes=(("Excel files", "*.xlsx"), ("All files", "*.*"))) if filename: prompts = load_prompts_from_excel(filename) if prompts: prompt_entry.delete(1.0, tk.END) # Clear current prompt # Insert multiple prompts with newlines prompt_entry.insert(tk.END, "\n".join(prompts)) def submit_and_display(prompt_entry, output_text, status_bar): """Handles submit button click.""" prompts = prompt_entry.get("1.0", tk.END).strip().split("\n") prompts = [p.strip() for p in prompts if p.strip()] if prompts: submit_button.config(state=tk.DISABLED) status_bar.config(text="Processing prompts...") output_text.config(state=tk.NORMAL) output_text.delete(1.0, tk.END) output_text.config(state=tk.DISABLED) # Start processing in a separate thread threading.Thread(target=process_prompts_threaded, args=(prompts, status_bar, output_text)).start() else: messagebox.showerror("Error", "Please enter or load some prompts.") status_bar.config(text="No prompts to process.") def process_prompts_threaded(prompts, status_bar, output_text): """Run process_prompts on a separate thread and re-enable the submit button.""" process_prompts(prompts, status_bar, output_text) root.after(0, lambda: submit_button.config(state=tk.NORMAL)) if name == " main ": root = tk.Tk() root.title("Flux Prompt App") # Input area prompt_label = tk.Label(root, text="Enter your prompt(s): (one per line)") prompt_label.pack() prompt_entry = scrolledtext.ScrolledText(root, height=10, width=60) prompt_entry.pack() # Button to open excel file browse_button = tk.Button(root, text="Load from Excel", command=lambda: browse_excel_file(prompt_entry)) browse_button.pack() # Submit button submit_button = tk.Button(root, text="Submit Prompt", command=lambda: submit_and_display(prompt_entry, output_text, status_bar)) submit_button.pack() # Output area output_text = scrolledtext.ScrolledText(root, height=10, width=60, state=tk.DISABLED) output_text.pack() # Status bar status_bar = ttk.Label(root, text="") status_bar.pack(side=tk.BOTTOM, fill=tk.X) root.mainloop()
