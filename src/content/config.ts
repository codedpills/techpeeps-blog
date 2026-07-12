import { defineCollection, z } from "astro:content";

// Frontmatter contract (PRD §6.3). A malformed draft fails the build.
const blog = defineCollection({
  type: "content",
  schema: z.object({
    title: z.string().min(1),
    description: z.string().min(1).max(155), // meta description
    pubDate: z.coerce.date(), // when the article was published on the site
    interviewDate: z.coerce.date().optional(), // YouTube publish date of the interview
    guest: z.string().min(1), // guest full name
    guestBio: z.string().min(1), // one line
    videoId: z.string().min(1), // primary YouTube id (for linking back)
    videoUrl: z.string().url(), // full watch URL
    sources: z.array(z.string()).optional(), // all source video ids for a multi-part story
    tags: z.array(z.string()).min(4).max(6), // 4-6
    heroClip: z.object({
      mp4: z.string(), // /clips/<slug>.mp4
      webm: z.string(), // /clips/<slug>.webm
      poster: z.string(), // /clips/<slug>.jpg
      alt: z.string().min(1), // accessibility description
    }),
    draft: z.boolean().optional().default(false),
  }),
});

export const collections = { blog };
