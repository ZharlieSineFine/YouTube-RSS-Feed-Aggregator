So what I want to build is an AI news aggregator
where I can take multiple sources. So
for example, YouTube channels and I want
for example blog posts from OpenAI and
Anthropic and I want to scrape those put
them into a database where we have some
kind of structure where we have sources
we have let‘s call them articles and
then what I want to do is I want to run
a daily digest where we're going to take
all of the articles from within that
time frame and we're going to do an LLM
summary around that and then based on
the user insights that we specify in
some kind of
agent system prompt. We can generate a
daily digest which is going to be short
snippets with a link to the original
source. Now from the YouTube channels I
want to I want to be able to create a
list of channels and then we want to get
the latest videos from those channels. I
think we can use the YouTube RSS feed
for that and for for the blog posts we
can just have URLs that we can scrape
for that. Okay. So I want everything
built in a Python back end. I want to
use a Postgress SQL database. I want to
use SQL alchemy in order to define the
database models and then to also create
the tables. I want the project structure
to be an app folder where all the app
logic is in. And then I also want a
docker folder where we first create a
very minimal setup for the Postgress SQL
database. And then that will probably be
starting point. We want to make sure
that later down the line, we can easily
deploy the whole app to render and then
also schedule it every 24 hours to run
the reports, get everything. And then
when we've created the daily digest, I
want to send an email to my personal
inbox with this. So that's that's what I
have in mind. I think that would be
pretty cool to build.


https://openai.com/news/

https://www.anthropic.com/research