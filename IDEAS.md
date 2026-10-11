AutoInvestigate
Cloud AI track theme is on the track challenges
Internal incubator for emerging technologies
“Takes the first steps in emerging technologies to deliver critical infrastructure and innovative solutions in:” Agentic AI, Superintelligence, Quantum
They have an interest in accelerating research of technologies:
For return on investment. Profit - new product or IP.

Our goal is to appeal to their capitalist mindset.

Parts
Website to interface with 2 and 3
Tree interface
Manual
Click on one idea to create a variatn of that idea
Or click multiple. Maybe we can combine them in some way add a prompt
We don’t want it to look like slop



Find emerging technologies AND create implementation ideas etc.
MVP: Emerging technologies are well known. List them.
Quantum computing, edge AI, machine learning artifacts, robot servants,   
Stretch: Look at arXiv

Create ideas for implementing these in novel ways
MVP: A small coding experiment
Stretch: Either for a market solution, a user interface, or to create IP (Patent)

Have $IDEA
Generate variants of the same ideas: How would this idea be different in a separate market or niche?
Vary the product would look different in United States vs Europe, different regulatory
Vary the idea itself. Maybe it should increase or decrease in scope
Vary the underlying technology. Maybe the same product idea would actually work with a slightly different technology
We want to maximally generate ideas, and then score them based on:
Tech risks, market, strategic fit, market horizon
Use decision makgin models?
Simulation?
Have user choose which variations they like, then continue.

Code and implement the ideas
MVP: Create tangible artifact
Stretch: Create larger project thing
Look at related github repositories so that we can borrow code/libraries/


At each stage, it should generate learnings for the swarm.


User’s Perspective
Give it abstract objectives. Look into “homomorphic encryption” (computing on encrypted data)


Value Generated
MVP: Give code snippets/ideas/projects to people in the org to continue their work
Stretch: Create whole products/OSS projects/patents & artifacts that automate the role of some people in the org 

Notices:
Smaller projects may be better. We don’t have the best models and our small ideas/code can be used by better agents (that cost more, we have less input) for further refine,refinement






Context
When AI Agents Disagree From collaboration to collective intelligence The challenge Can you build AI agents that work together, adapt to changing conditions, and make decisions even when they disagree? Individual agents can reason, use tools, and solve complex problems. This challenge asks what happens when independent agents bring different capabilities, incomplete information, competing priorities, or conflicting recommendations to the same problem. 

LEVEL 3 · BUILD A COLLECTIVE INTELLIGENCE At least three autonomous agents with competing objectives that deliberate, negotiate, and try to reach consensus without a central decision-maker. Examples: energy agents balancing cost, sustainability, and reliability; emergency agents negotiating scarce resources; research agents weighing conflicting hypotheses. Success: genuine disagreement, a real deliberation or negotiation mechanism, the effect of new information, and a comparison against a simpler baseline. Consensus is not always the right outcome; explain when the system should stop, keep the disagreement, or ask a human.

Backend Code A
Part 1: Research
Do very deep, super deep research on a topic and learn as much as you can, as an expert, on the topic. After researching.
BACKEND Code B
The backend should have three parts. For each part, generate a markdown file for how to use the backend routes from the perspective of the frontend.
Part 1: Idea generation
This part is responsible for generating the ideas. I want you to create multiple variations of an LLM pipeline. The pipeline should be simple and use models that are configured by the user.

The INPUT is:
A model identifier
API keys for the model (this always lives on the backend)
ONE OR MORE IDEAS.
An “idea iteration type” of what manipulation to do for the idea. There are several different types:

Idea Iteration Types:
Refinement. Take one or more ideas that are not really well-developed, and refine them, using real-world research and projects and stuff about the world to create something specific.
Variation and Generation: Take one or more ideas that are good, and create multiple variations of each. From the input, be able to generate multiple new ideas, and have that be configurable via API input. For example, it may serve different markets. Use an agent or skill to help generate these ideas thinking about a specialization. For example, a business person may have idea of how to do this, software person may have an idea of how to do this, etc.
Consolidation: Take one or more ideas, and consolidate them in a way that is useful, given all the background research.
Part 2: Idea evaluation
So this part is going to be evaluating the ideas that have been generated. The routes should expect a single idea that’s a string for you to evaluate. The same idea string will be imputed into each GROUP PERSPECTIVE. There will be multiple GROUP PERSPECTIVES that each are tailored to different groups of people with different needs or wants or goals.

Represent the group perspectives as an array of objects, with each object being a group perspective. Each object should have a property called “agents”. Each person/agent will have a property of “model” and “api_key” for that model. The models will be configurable via the frontend settings, I want you to generate a “/settings” page that is as bare HTML as possible with just the config options, but add JS when needed.

By default, create the e have the following:

The PROFESSIONAL RESEARCH GROUP PERSPECTIVE: By default there should be 4 research professionals talking. They should know what stage of the research process the idea is in, is it feasible to scale up, are there only long term implementations, etc.
The PRIVATE EQUITY/BUSINESS PERSPECTIVE: Similar with nerd, there should be 4 private equity people. Each agent should be a private equity partner and think about how the business can be best positioned to maximize returns. Use the these criteria (maybe one for each agent) that we give and create a good default for the private equity to deliberate: tech risk (avoids ideas likely to fail technically), market (picks ideas with clear buyers/demand), strategic_fit (picks ideas that build on existing platforms), horizon (balance near term payoff vs long-term benefits)
The MARKET REACTION PERSPECTIVE: Similar with the others, create 5 agents by default that ARE the people that you are trying to serve. Think about whether they will have a positive reaction or negative reaction. These people won’t naturally come to a consensus, but should be different archtypes of people. For example, the “power user”, the “person that loves to use the free tier”. By default only use 5 agents but create a bunch of people/customer archetypes that can be used

Once you give the idea prompt string to each group perspective, tell them to deliberate for a configurable amount of seconds. And tell them, based on their prompt, to output an evaluation. Tell them to FEEL FREE AND ENCOURAGE to use The Jev/TypeSafe AI model for evaluation and also any open decision model. All models should be used through OpenRouter.

Then, for each group perspective, I want you to summarize the main pros and cons, but keep the important details, make the model to use for this configurable in the fronend settings.

Take each summarized model, and give each GROUP PERSPECTIVE the summarized models. For each of them, I want you to use the markdown prompts from before to generate whatever it says, pros and cons, scores for feasability on whatever metrics make sense. Create a good default markdown document.

Do THIS ONE MORE TIME.

After this, then I want you to use a “should we stop or go” prompt. This prompt should ask if we should actually come to a consensus or not from all the different agents. Is it actually feasible or not? Use the prompt to create pros and cons and rationales for each. This is what will be shown to the user, so it should not look like LLM text.

If you should continue go back to the “deliberate for a configurable amount of seconds” ONE MORE TIME, and then ALWAYS FINISH, then go below.

If you should stop, then stop. Give the user the final text/conclusions for each nerd group.









Be able to configure all prompts with a file on the file system and be able to select them in the settings page.








