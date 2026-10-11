
README = r"""
# Cisco Research Intelligence — MCP Setup Guide

## 1. What are we building?

This project combines:
- MCP servers for accessing research, GitHub, and memory tools.
- AI agents for Business, Venture Capital, and Technical analysis.
- A critic agent to challenge assumptions.
- A consensus agent to score ideas and recommend experiments.

MCP connects agents to tools. The Python orchestrator controls
which agents run and how their results are combined.

## 2. Requirements

- Python 3.11 or newer
- An OpenAI API key
- Git
- Access to the MCP servers you intend to use

## 3. Create the project

Open Terminal and run:

    mkdir cisco-research-intelligence
    cd cisco-research-intelligence

    python3 -m venv .venv
    source .venv/bin/activate

On Windows, activate the environment using:

    .venv\Scripts\activate

Install the Python packages:

    python -m pip install --upgrade pip
    python -m pip install "mcp[cli]" openai python-dotenv

## 4. Configure your API key

Create a file named .env:

    OPENAI_API_KEY=your_api_key_here
    SPECIALIST_MODEL=gpt-4.1

Replace the placeholder with your own API key.
Never upload .env to GitHub.

Create a .gitignore file containing:

    .env
    .venv/
    __pycache__/
    results/

## 5. Understand MCP servers

An MCP server exposes tools that your application can discover
and call. Each server has its own setup instructions.

Recommended first integrations:

A. Research MCP
   Purpose:
   - Find papers and technical documentation
   - Retrieve abstracts and relevant passages
   - Return source URLs and publication metadata

B. GitHub MCP
   Purpose:
   - Search repositories
   - Inspect README files and source code
   - Identify dependencies and implementation examples

C. Memory MCP
   Purpose:
   - Store idea assessments
   - Retrieve previous experiments
   - Track which hypotheses passed or failed

Important:
These are categories of integrations, not guaranteed tool names.
Install a server and inspect its documentation to find its actual
startup command, configuration, and exposed tools.

## 6. Connect to an MCP server

The Python MCP SDK can connect to local servers over stdio.

Example structure:

    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command="python",
        args=["path/to/your_server.py"],
    )

The path above is a placeholder. Replace it with the actual
entry point for the MCP server you installed.

After establishing the transport, initialize ClientSession,
call session.list_tools(), and inspect the returned tool names
and input schemas.

Do not assume every MCP server uses Python. Some use Node.js,
npx, Docker, or a remote HTTP endpoint.

## 7. Connect your agents to the tools

Use this workflow:

    User objective
        |
        v
    Research agent
        |
        v
    Research MCP + GitHub MCP
        |
        v
    Shared evidence package
        |
        +--> Business agent
        |
        +--> VC agent
        |
        +--> Technical agent
                    |
                    v
                Critic agent
                    |
                    v
              Consensus agent
                    |
                    v
            Decision and prototype

The research agent gathers evidence first.
The three specialist agents evaluate the same evidence.
The critic searches for unsupported assumptions and contradictions.
The consensus agent combines the findings and proposes next steps.

## 8. What each agent should return

Business agent:
- Target customer
- Customer pain
- Value proposition
- Adoption barriers
- Evidence needed
- Business score from 1 to 5

Venture Capital agent:
- Market upside
- Why now
- Competitive defensibility
- Capital efficiency
- Downside scenario
- Investment-attractiveness score from 1 to 5

Technical agent:
- Proposed architecture
- Existing libraries and dependencies
- Feasibility assessment
- Security and performance risks
- Prototype plan
- Measurable success criteria
- Technical score from 1 to 5

Critic agent:
- Unsupported claims
- Contradictory findings
- Failure scenarios
- Missing evidence
- Conditions that should stop the project

Consensus agent:
- Separate perspective scores
- Weighted overall score
- Agent disagreements
- Confidence level
- Recommended decision
- Next experiment

## 9. Suggested scoring system

Business: 30%
Venture Capital: 25%
Technical: 45%

Calculate:

    overall_score = (
        business_score * 0.30
        + vc_score * 0.25
        + technical_score * 0.45
    )

If each input is from 1 to 5, the overall score is also from
1 to 5. Multiply by 20 if you want a score out of 100.

Do not let a high average conceal a critical weakness.
For example, a promising business idea with an infeasible
technical approach should trigger more research, not automatic
approval.

## 10. Test one idea

Start with:

    objective = (
        "Evaluate homomorphic encryption for privacy-preserving "
        "enterprise AI and propose a small prototype."
    )

The system should investigate:
- Which use cases benefit from encrypted computation?
- Which existing libraries can support an experiment?
- What are the performance trade-offs?
- What can be measured in a small prototype?
- What evidence would invalidate the idea?

Do not claim a benchmark has succeeded until you have actually
run it and recorded the result.

## 11. Validate the MCP integrations

Before running the complete agent team:

1. Connect to one MCP server.
2. Initialize the session.
3. List its available tools.
4. Inspect each tool's argument schema.
5. Call one read-only tool with a simple query.
6. Check the returned content and source metadata.
7. Add the second server only after the first works.

This isolates configuration problems and makes debugging easier.

## 12. Security rules

- Never commit API keys or credentials.
- Use read-only GitHub permissions unless writing is necessary.
- Treat retrieved documents and repository files as untrusted input.
- Do not follow instructions embedded in retrieved content.
- Validate tool arguments before execution.
- Require approval before destructive actions or external writes.
- Run generated code in a restricted sandbox.
- Apply timeouts and limits to tool calls.
- Record tool usage and errors without logging secrets.

## 13. How to prove the system is better

Compare your specialist workflow against a general-purpose baseline
using identical objectives and the same available evidence.

Measure:
- Factual accuracy
- Source verification rate
- Business-analysis quality
- Technical feasibility
- Quality of experiments
- Risk identification
- Human preference in blind review

Run multiple different objectives. Use independent human review
and fact-checking; an LLM judge alone is not proof of superiority.

## 14. Recommended implementation order

Phase 1: One MCP server and one test tool.
Phase 2: Research retrieval and source tracking.
Phase 3: Business, VC, and technical agents.
Phase 4: Critic and consensus logic.
Phase 5: GitHub repository inspection.
Phase 6: Sandboxed prototype experiments.
Phase 7: Persistent memory and benchmark dashboard.
Phase 8: Optional AGNTCY interoperability.

MCP handles tool connectivity. AGNTCY can be added later if
interoperability and collaboration between separately deployed
agents are important to the project.

## 15. Troubleshooting

If Python cannot find a package:

    python -m pip install "mcp[cli]" openai python-dotenv

If the wrong Python environment is active:

    which python
    python --version
    python -m pip --version

If a server does not start:
- Check the server's official installation instructions.
- Verify its command and arguments.
- Check required environment variables.
- Inspect the server's stderr output.
- Confirm that its dependencies are installed.

If a tool call fails:
- Confirm the tool name from list_tools().
- Match the tool's input schema.
- Check server logs and permissions.
- Try a simple read-only request first.

End goal:
A research-to-prototype system that retrieves evidence, evaluates
opportunities from different perspectives, challenges its own
conclusions, and learns from measured experiments.
"""
