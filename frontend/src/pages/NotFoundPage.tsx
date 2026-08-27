import { Link, useLocation } from 'react-router-dom'
import { Compass } from 'lucide-react'

import { EmptyState } from '@/components/common/EmptyState'

export function NotFoundPage() {
  const location = useLocation()

  return (
    <div className="grid h-full place-items-center p-6">
      <EmptyState
        icon={Compass}
        title="Page not found"
        description={`Nothing is routed at ${location.pathname}.`}
        action={
          <div className="flex flex-wrap items-center justify-center gap-2">
            <Link to="/dashboard" className="btn-primary !text-xs">
              Go to dashboard
            </Link>
            <Link to="/experiment" className="btn-secondary !text-xs">
              Experiment workspace
            </Link>
          </div>
        }
      />
    </div>
  )
}
