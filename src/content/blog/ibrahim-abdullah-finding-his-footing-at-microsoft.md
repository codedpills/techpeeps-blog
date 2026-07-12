---
title: "He Wondered If Microsoft Had Hired Him by Mistake. Then He Found His Footing."
description: A Ghanaian software engineer on discovering himself in computer science,
  surviving imposter syndrome, and why you should master one language first.
pubDate: '2026-07-22'
guest: Ibrahim Abdullah
guestBio: Software engineer at Microsoft on the Office engineering team, building
  developer tooling and test frameworks. Ashesi University graduate from Ghana, based
  in Vancouver.
videoId: iPFVpA7s6Zs
videoUrl: https://www.youtube.com/watch?v=iPFVpA7s6Zs
tags:
- software engineering
- Microsoft
- career journey
- imposter syndrome
- Ghana
- diaspora
heroClip:
  mp4: /clips/ibrahim-abdullah-finding-his-footing-at-microsoft.mp4
  webm: /clips/ibrahim-abdullah-finding-his-footing-at-microsoft.webm
  poster: /clips/ibrahim-abdullah-finding-his-footing-at-microsoft.jpg
  alt: Ibrahim Abdullah speaking about his journey to Microsoft
draft: true
interviewDate: '2022-08-29'
---

# He Wondered If Microsoft Had Hired Him by Mistake. Then He Found His Footing.

There is a moment early in Ibrahim Abdullah's first weeks at Microsoft that most engineers will recognize, even if they would never say it out loud. He had just moved to Vancouver, joined a team writing in C#, Perl, C++, and languages he barely recognized, and he found himself calling up a colleague to ask, in effect, whether a mistake had been made. "Wait, how, how, why did you people hire me here?" he remembers thinking. He wondered, half seriously, whether he had been a diversity hire, because, in his words, "all the things that you guys are doing, it seems like I know nothing about it."

Three years later, he laughs about it. But that gap, between how it felt and how it turned out, is the through-line of his whole story. It is a story worth slowing down for.

## What a software engineer actually does at Microsoft

When people picture the job, they picture code. Ibrahim is quick to complicate that. He works on the Office engineering side, building the systems that other product teams (the folks shipping Excel, Word, PowerPoint) rely on to do their own engineering. His domain is a test framework, a test runtime, and the harnesses developers use to write and run their unit and integration tests, whether in an automation lab or as part of the build system.

In other words, his customers are other engineers at Microsoft. That shapes the rhythm of his days. Some of it is feature work: design first, get teammates to review, then implement once they sign off. Some of it is being on call, monitoring the systems he owns and responding when something breaks in production, deciding whether to fix forward or roll back.

And a surprising amount of it, he says, is not code at all. "It's not always about writing code as people think software engineering is." There is design, cost (how much Azure a feature will consume), and the endless negotiation of trade-offs. His favorite illustration: shipping something that shaves a developer's pain but adds "2 seconds, 3 seconds" to their build time, and deciding, together, whether it is worth it. Building for other developers is its own art, because "every other developer has an opinion." The craft, he explains, is often about giving people the option to turn a feature off if they do not want it, and on if they do.

Readers hoping the coding part survives all this will be relieved. Asked for his favorite part, Ibrahim does not hesitate: "for most people we will all say it's the coding part," the thrill of translating a design document into something that works, and the particular satisfaction of going "one level below to get this thing to work so that other people can build on top of it."

## Rewinding: how little Ibrahim got here

I always want to rewind with a guest, because the polished present rarely explains itself. Ibrahim's beginnings are a lesson in redirection.

In high school he studied science, but with geography instead of biology, a small act of rebellion against a father who thought medicine would be fine. "I don't want to be it," he decided, "if that's the case, I'm not going to do biology, so that cancels me out." His actual dream was petroleum engineering, chasing the logic of a young man who had heard Ghana found oil and reasoned there would be jobs.

Things did not go as planned. After high school he spent a year at home, working, gathering money for university. It was in that gap that he found Ashesi, its scholarship, and its computer science program. Given his science background, the choice made itself.

What is refreshing is how honestly he describes the four years that followed. He was not the classmate confidently building mobile and web apps. "Building actual software, I wasn't really into it." He loved the theory (a data structures class could light him up) but he was also caught in the churn every self-taught learner knows: HTML and CSS, then someone is doing JavaScript, then Java, then machine learning, then data science. "So I was kind of going those kind of back and forth, back and forth thing," he says. Only near graduation did the shape of his interest emerge. He was drawn to developer platforms and build systems, work that "even though it's software engineering, it's engineering, it highly incorporates computer science concepts."

Along the way he stacked up experiences that, in hindsight, all pointed somewhere. There was an early, humbling internship (a bit of PHP, a bit of MySQL) where he "couldn't really build anything exciting" but got his first taste of working for a company. There was a stint at a biometric software firm, Jenki, where an individual inventory project went well enough that they floated future opportunities. And there was a summer in the US, through a College of Wooster program, working with a startup using software to identify young people's talents.

## The part that looked easy but wasn't

When Microsoft finally came along, Ibrahim describes it plainly: "it just fit. I was just a good fit at the point, at that point in time." It is the kind of sentence that hides an enormous amount of work, and I pushed on it, because most of us never get to see the backstage.

The backstage was years of deliberate preparation. Hackathons, including Google HashCode, where he first scored no points, then a few the next year, and slowly learned "some of the things that I have to do or I have to learn if I want to get into companies like this." There was also a genuinely heartbreaking near-miss: in 2017, he and friends won a Microsoft hackathon in Ghana, part of the Africa to Redmond program, "and we didn't hear from them again."

Rather than let that close the door, he treated it as a signal that another cohort might come, and he prepared accordingly. He was intentional about doing his national service at Ashesi partly for the free internet, and he became known for it. "I will come to school and I will stay there a very long time, deep in the night, like around 12 midnight," he recalls, sometimes leaving at 5 a.m. He was working through *Grokking the Coding Interview* and drilling LeetCode with a friend on midnight calls. He even chose which courses to teach as a teaching assistant (software engineering, data structures and algorithms, system design) to keep himself sharp.

And he is generous about who helped. His now-wife ran mock interviews with him, playing, as he puts it, a "top tech executive sort of thing." It is the kind of detail that reframes the word "fit" entirely. Ibrahim did not stumble into Microsoft. He spent years quietly getting ready for it.

## Imposter syndrome, and the engineer with gray hair

I told Ibrahim about my own habit of bracing for the moment a new team might "find out I'm a fraud," and he did not flinch. His first months in Vancouver were, in his word, "overwhelming." New country, new weather, no family nearby, a codebase full of languages he had never touched, and colleagues who seemed to be operating on another level. He remembers being so exhausted after work that a friend came to visit and could not wake him.

What he did next is the most quietly instructive part of the whole conversation. He named it. In week one or two he went to his manager and asked, directly, for a mentor to help him understand the landscape. That mentor (now his engineering manager) met with him monthly for a year, patiently explaining how the engineering systems worked. From there came his first project, and a small, unforgettable ritual: checking in his first pull request and just staring at it. "I have a code in Microsoft code base and people are using it into production."

The reframe that stuck with him came from a principal engineer who has been at Microsoft "for over 30 years," gray hair and all. This veteran admitted that every time he starts a new project, the imposter syndrome returns. "For me, that was like a reality check," Ibrahim says. "It's just something that you have to know how to deal with, but everybody will experience this."

His own diagnosis is gentle and true: "change is difficult." One step in, two steps in, and the unfamiliar becomes familiar.

## The advice: pick one language, learn the principles

Given the chance to start over, Ibrahim would change one thing, and it is the same churn he described from his student days. "I wouldn't worry so much about all the different things that are going on." His counsel is to pick a single language, say Java, and stay with it: learn the concepts, the data structures, the algorithms, and do as much as you possibly can with it. "If you understand the programming concepts, you understand software engineering, it doesn't really matter what programming language you're going to work with."

He has lived the proof. In a one-week gig in Ghana, he was handed a Python task without knowing Python. "I was like, okay, give me 2 days, let me learn Python," he says. He sat in the office learning it, and by the end of the week had built service hooks that pushed job-application notifications to Slack and email. The syntax was new; the thinking was not. "I know what for loop is, I know what if statement is," he says. The rest transfers.

For anyone entering the field now, that is his whole message: stop chasing the newest framework and go deep on the fundamentals, because those are the parts that travel with you.

## Closing thought

What lingers, listening to Ibrahim, is how ordinary his extraordinary story sounds in his own telling. A redirected dream, a gap year, a period of not knowing what he was good at, a heartbreaking rejection, and then years of unglamorous, midnight preparation that eventually looked, from the outside, like a lucky fit. He is proof that "discovering yourself," as he keeps calling it, is not a detour from the career. It is the career.

I came away a little lighter about my own bracing-for-fraud instincts, and, as a bonus, learned mid-conversation that he is married (news to me). The world is better for engineers who build the tools other engineers stand on, and who are this honest about the climb.

You can watch the full conversation with Ibrahim Abdullah in the linked video above.
