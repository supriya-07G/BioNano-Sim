import { createBrowserRouter } from 'react-router-dom'

import { AppShell } from '@/components/layout/AppShell'
import { ComparePage } from '@/pages/ComparePage'
import { DashboardPage } from '@/pages/DashboardPage'
import { ExperimentPage } from '@/pages/ExperimentPage'
import { HistoryPage } from '@/pages/HistoryPage'
import { LandingPage } from '@/pages/LandingPage'
import { MethodologyPage } from '@/pages/MethodologyPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { ResultsPage } from '@/pages/ResultsPage'
import { SimulationPage } from '@/pages/SimulationPage'

export const router = createBrowserRouter([
  // The landing page stands outside the app shell: it has its own full-bleed hero.
  { path: '/', element: <LandingPage /> },
  {
    element: <AppShell />,
    children: [
      { path: '/dashboard', element: <DashboardPage /> },
      { path: '/experiment', element: <ExperimentPage /> },
      { path: '/simulation', element: <SimulationPage /> },
      { path: '/simulation/:jobId', element: <SimulationPage /> },
      { path: '/results', element: <ResultsPage /> },
      { path: '/results/:jobId', element: <ResultsPage /> },
      { path: '/results/precomputed/:pdbId', element: <ResultsPage /> },
      { path: '/compare', element: <ComparePage /> },
      { path: '/compare/:jobIdA/:jobIdB', element: <ComparePage /> },
      { path: '/history', element: <HistoryPage /> },
      { path: '/methodology', element: <MethodologyPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])
