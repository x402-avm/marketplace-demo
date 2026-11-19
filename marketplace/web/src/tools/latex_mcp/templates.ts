/** Starter documents that fill the editor. Each one compiles with a standard TeX Live install. */
export interface Starter {
  id: string
  name: string
  source: string
}

export const STARTERS: Starter[] = [
  {
    id: 'article',
    name: 'Article',
    source: String.raw`\documentclass[11pt]{article}
\usepackage[margin=1in]{geometry}

\title{Tide Pools of the Northern Coast}
\author{Ana Ribeiro}
\date{\today}

\begin{document}
\maketitle

\section{Introduction}
Tide pools hold a small, crowded world that is flooded and
drained twice a day. This note records what we counted on
three visits in early spring.

\section{Method}
We marked ten pools and counted every animal larger than a
fingernail at low tide.

\begin{itemize}
  \item Sea stars and urchins were counted by hand.
  \item Snails were counted in a 20 cm square.
\end{itemize}

\section{Findings}
Pools nearer the low-water line held twice as many species
as pools near the cliff.

\end{document}
`,
  },
  {
    id: 'letter',
    name: 'Letter',
    source: String.raw`\documentclass[11pt]{letter}
\usepackage[margin=1in]{geometry}

\signature{Ana Ribeiro}
\address{14 Harbour Road \\ Porto \\ Portugal}

\begin{document}
\begin{letter}{Dr. Sam Okafor \\ Marine Institute \\ 2 Quay Street \\ Lisbon}

\opening{Dear Dr. Okafor,}

Thank you for sending the survey notes from the March visit.
I have compared them with our own counts and the two sets agree
for nine of the ten pools.

I would be glad to share the full table before the meeting on
the 12th.

\closing{With best regards,}

\end{letter}
\end{document}
`,
  },
  {
    id: 'equations',
    name: 'Equation sheet',
    source: String.raw`\documentclass[11pt]{article}
\usepackage[margin=0.9in]{geometry}
\usepackage{amsmath, amssymb}
\pagestyle{empty}

\begin{document}
\section*{Calculus reference}

\subsection*{Derivatives}
\begin{align*}
  \frac{d}{dx} x^n &= n x^{n-1} \\
  \frac{d}{dx} e^{x} &= e^{x} \\
  \frac{d}{dx} \ln x &= \frac{1}{x}
\end{align*}

\subsection*{Integrals}
\begin{align*}
  \int x^n \, dx &= \frac{x^{n+1}}{n+1} + C, \quad n \neq -1 \\
  \int_0^\infty e^{-x^2} \, dx &= \frac{\sqrt{\pi}}{2}
\end{align*}

\subsection*{Series}
\[
  e^{x} = \sum_{k=0}^{\infty} \frac{x^k}{k!}
  \qquad
  \frac{1}{1-x} = \sum_{k=0}^{\infty} x^k, \quad |x| < 1
\]

\end{document}
`,
  },
]
