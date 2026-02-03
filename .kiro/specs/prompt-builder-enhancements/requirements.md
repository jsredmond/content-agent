# Requirements Document

## Introduction

This document specifies requirements for enhancing the PromptBuilder class and ContentGenerator in the Content Agent's LinkedIn post generation pipeline. The enhancements focus on improving hook variety in generated posts, limiting hashtag output, adding a validation gate for article quality, and updating the default LLM model for better creative writing.

## Glossary

- **PromptBuilder**: Class responsible for constructing prompts for LinkedIn post generation using the Hook-Value-CTA framework.
- **ContentGenerator**: Main class for transforming scraped article content into LinkedIn posts using Ollama LLM.
- **Hook**: The attention-grabbing opening section of a LinkedIn post.
- **ScoredArticle**: Dataclass containing article data with relevance and recency scores.
- **score_overall**: Weighted score (0-100) combining recency and relevance scores for an article.
- **Hashtag**: A word or phrase preceded by a hash sign (#) used on social media to identify content.
- **Validation_Gate**: A filter that prevents processing of articles below a quality threshold.

## Requirements

### Requirement 1: Hook Variety Instructions

**User Story:** As a content creator, I want the LLM to use varied hook styles, so that my LinkedIn posts don't all start with questions and feel repetitive.

#### Acceptance Criteria

1. THE PromptBuilder SHALL include instructions for three specific hook styles: Bold Statement, Contrarian View, and Fact-Driven
2. THE PromptBuilder SHALL instruct the LLM to avoid starting every post with a question
3. WHEN building a prompt, THE PromptBuilder SHALL include a description for Bold Statement as "A confident, declarative opening"
4. WHEN building a prompt, THE PromptBuilder SHALL include a description for Contrarian View as "Challenge conventional wisdom"
5. WHEN building a prompt, THE PromptBuilder SHALL include a description for Fact-Driven as "Lead with a compelling statistic or data point"

### Requirement 2: Hashtag Limit

**User Story:** As a content creator, I want exactly 3 hashtags per post, so that my posts look clean and focused without hashtag overload.

#### Acceptance Criteria

1. THE PromptBuilder SHALL instruct the LLM to output exactly 3 hashtags
2. WHEN building a prompt, THE PromptBuilder SHALL instruct the LLM to select only the 3 most relevant hashtags from the provided list
3. THE PromptBuilder SHALL include explicit instruction that the output must contain no more and no fewer than 3 hashtags

### Requirement 3: Validation Gate for Article Quality

**User Story:** As a content pipeline operator, I want to skip low-quality articles automatically, so that I don't waste LLM resources on content unlikely to produce good posts.

#### Acceptance Criteria

1. WHEN generate_batch processes articles, THE ContentGenerator SHALL skip any article with score_overall below 50
2. WHEN an article is skipped due to low score, THE ContentGenerator SHALL log a message indicating the article was skipped
3. WHEN an article is skipped due to low score, THE ContentGenerator SHALL NOT include it in the failed list
4. THE BatchResult SHALL accurately reflect only articles that were actually processed (not skipped)

### Requirement 4: Default Model Update

**User Story:** As a content creator, I want the generator to use a model optimized for creative writing, so that my LinkedIn posts are more engaging.

#### Acceptance Criteria

1. THE ContentGenerator SHALL use "llama4:scout" as the default model
2. WHEN no model is specified in the constructor, THE ContentGenerator SHALL default to "llama4:scout"
3. THE ContentGenerator SHALL still support custom model configuration via constructor parameter
