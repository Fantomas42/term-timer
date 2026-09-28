"""Flask web server for solve statistics and visualization."""
import os
import threading
import webbrowser
from wsgiref.simple_server import WSGIRequestHandler

from bottle import TEMPLATE_PATH
from bottle import Bottle
from bottle import HTTPError
from bottle import HTTPResponse
from bottle import redirect
from bottle import request
from bottle import static_file

from term_timer.constants import STATIC_DIRECTORY
from term_timer.constants import TEMPLATES_DIRECTORY
from term_timer.interface.console import console
from term_timer.server.views import AcademyCaseAlgorithmsDebugView
from term_timer.server.views import AcademyCaseView
from term_timer.server.views import AcademyStepView
from term_timer.server.views import AcademyView
from term_timer.server.views import AlgorithmDetailView
from term_timer.server.views import CubeImageView
from term_timer.server.views import CubeRenderView
from term_timer.server.views import DailyDayView
from term_timer.server.views import DailyListView
from term_timer.server.views import DailySolveDeleteView
from term_timer.server.views import DailySolveDetailView
from term_timer.server.views import DailySolveUpdateCommentView
from term_timer.server.views import DailySolveUpdateFlagView
from term_timer.server.views import DesignStyleguideView
from term_timer.server.views import Error404View
from term_timer.server.views import Error500View
from term_timer.server.views import ScrambleDetailView
from term_timer.server.views import ScrambleHomeView
from term_timer.server.views import SessionDetailView
from term_timer.server.views import SessionListView
from term_timer.server.views import SolveDeleteView
from term_timer.server.views import SolveDetailView
from term_timer.server.views import SolveUpdateCommentView
from term_timer.server.views import SolveUpdateFlagView
from term_timer.server.views import StyleguideView
from term_timer.server.views import TrainingForecastView
from term_timer.server.views import TrainingReviewView


class RichHandler(WSGIRequestHandler):
    """Custom WSGI request handler with Rich console logging."""

    def log_request(self, code: int | str = '-', size: int | str = '-') -> None:
        """
        Log HTTP request with colored Rich console output.

        Args:
            code: HTTP status code.
            size: Response size in bytes.

        """
        klass = 'green'
        if int(code) > 400:
            klass = 'red'

        message = (
            f'[server][{ self.log_date_time_string() }][/server] '
            f'[{ klass }]{ code!s }[/{ klass }] '
            f'[result]{ self.requestline }[/result] '
            f'[comment]{ size!s }[/comment]'
        )

        console.print(message)


class Server:
    """Flask/Bottle web server for solve statistics and visualization."""

    def run_server(self, host: str, port: int, *, debug: bool) -> None:
        """
        Start the web server and open browser.

        Args:
            host: Host address to bind to (e.g., 'localhost', '0.0.0.0').
            port: Port number to listen on.
            debug: Enable debug mode with auto-reload on code changes.

        """
        TEMPLATE_PATH.insert(0, TEMPLATES_DIRECTORY)

        app = self.create_app(debug=debug)

        if not os.getenv('BOTTLE_CHILD'):
            url = f'http://{ host }:{ port }/'
            console.print(
                '[server]Term Timer server is listening on [/server]'
                f'[localhost][link={ url }]{ url }[/link][/localhost]',
            )
            console.print('Hit Ctrl-C to quit.', style='comment')

            # Open browser in a separate thread
            def open_browser() -> None:
                webbrowser.open(url)

            if not debug:
                threading.Thread(target=open_browser, daemon=True).start()

        app.run(
            host=host,
            port=port,
            quiet=True,
            reloader=debug,
            debug=debug,
            server='wsgiref',
            handler_class=RichHandler,
        )

    @staticmethod
    def add_daily_routes(app: Bottle, *, debug: bool) -> None:
        """
        Register the routes of the daily sessions.

        A daily session is addressed by its day, which rules out 'all':
        the days of the daily directory are never pooled together.

        Args:
            app: Bottle application to register the routes on.
            debug: Enable debug mode for detailed error pages.

        """
        day_url = r'/daily/<cube:int>/<day:re:\d{4}-\d{2}-\d{2}>/'
        solve_url = f'{ day_url }<solve:int>/'

        @app.route('/daily/<cube:int>/')  # type: ignore[untyped-decorator]
        def daily_list(cube: int) -> str:
            """
            Render the daily hub listing every daily session.

            Returns:
                Rendered HTML template.

            """
            return DailyListView(cube).legacy(
                v1='v1' in request.GET,
            ).as_view(debug)

        @app.route(f'{ solve_url }flag/', method='POST')  # type: ignore[untyped-decorator]
        def daily_solve_update_flag(cube: int, day: str, solve: int) -> None:
            """Handle daily solve update flag POST request."""
            DailySolveUpdateFlagView(
                cube, day, solve,
                request.POST.flag,
            )

        @app.route(f'{ solve_url }comment/', method='POST')  # type: ignore[untyped-decorator]
        def daily_solve_update_comment(
                cube: int, day: str, solve: int,
        ) -> None:
            """Handle daily solve update comment POST request."""
            DailySolveUpdateCommentView(
                cube, day, solve,
                request.POST.comment,
            )

        @app.route(f'{ solve_url }delete/', method='POST')  # type: ignore[untyped-decorator]
        def daily_solve_delete(cube: int, day: str, solve: int) -> None:
            """Handle daily solve delete POST request."""
            DailySolveDeleteView(cube, day, solve)

        @app.route(solve_url)  # type: ignore[untyped-decorator]
        def daily_solve_detail(cube: int, day: str, solve: int) -> str:
            """
            Render a daily attempt detail page with analysis.

            Returns:
                Rendered HTML template.

            """
            return DailySolveDetailView(
                cube, day, solve,
                request.GET.m,
                request.GET.o or 'auto',
            ).legacy(v1='v1' in request.GET).as_view(debug)

        @app.route(day_url)  # type: ignore[untyped-decorator]
        def daily_day(cube: int, day: str) -> str:
            """
            Render the attempts of one daily session.

            Returns:
                Rendered HTML template.

            """
            return DailyDayView(cube, day).legacy(
                v1='v1' in request.GET,
            ).as_view(debug)

    @staticmethod
    def add_academy_routes(app: Bottle, *, debug: bool) -> None:
        """
        Register the routes of the academy pages.

        Args:
            app: Bottle application to register the routes on.
            debug: Enable debug mode for template rendering.

        """
        @app.route('/academy/')  # type: ignore[untyped-decorator]
        def academy_overview() -> str:
            """
            Render academy overview page.

            Returns:
                Rendered HTML template.

            """
            return AcademyView(
                orientation=request.GET.o,
                mode=request.GET.m,
                cube_size=request.GET.c,
                palette=request.GET.p,
            ).legacy(v1='v1' in request.GET).as_view(debug)

        @app.route('/academy/<method>/<step>/')  # type: ignore[untyped-decorator]
        def academy_step(method: str, step: str) -> str:
            """
            Render academy step page with all cases.

            Returns:
                Rendered HTML template.

            """
            return AcademyStepView(
                method, step,
                request.GET.group,
                request.GET.family,
                request.GET.o,
                mode=request.GET.m,
                cube_size=request.GET.c,
                palette=request.GET.p,
            ).legacy(v1='v1' in request.GET).as_view(debug)

        @app.route('/academy/<method>/<step>/<case_id>/')  # type: ignore[untyped-decorator]
        def academy_case(method: str, step: str, case_id: str) -> str:
            """
            Render academy case detail page.

            Returns:
                Rendered HTML template.

            """
            return AcademyCaseView(
                method, step, case_id,
                request.GET.o,
                mode=request.GET.m,
                cube_size=request.GET.c,
                palette=request.GET.p,
            ).legacy(v1='v1' in request.GET).as_view(debug)

        @app.route('/academy/<method>/<step>/<case_id>/debug/')  # type: ignore[untyped-decorator]
        def academy_case_algorithms_debug(
                method: str, step: str, case_id: str,
        ) -> str:
            """
            Render academy case algorithms debug page.

            Returns:
                Rendered HTML template.

            """
            return AcademyCaseAlgorithmsDebugView(
                method, step, case_id,
                request.GET.o,
                mode=request.GET.m,
                cube_size=request.GET.c,
                palette=request.GET.p,
            ).legacy(v1='v1' in request.GET).as_view(debug)

    @staticmethod
    def add_training_routes(app: Bottle, *, debug: bool) -> None:
        """
        Register the routes of the training pages.

        Args:
            app: Bottle application to register the routes on.
            debug: Enable debug mode for template rendering.

        """
        @app.route('/training/')  # type: ignore[untyped-decorator]
        def training_forecast() -> str:
            """
            Render the training status and review forecast page.

            Returns:
                Rendered HTML template.

            """
            return TrainingForecastView().legacy(
                v1='v1' in request.GET,
            ).as_view(debug)

        @app.route('/training/<method>/<step>/review/')  # type: ignore[untyped-decorator]
        def training_review(method: str, step: str) -> str:
            """
            Render the review sheet of a step.

            Returns:
                Rendered HTML template.

            """
            return TrainingReviewView(
                method, step,
                pool=request.GET.pool,
                family=request.GET.family,
            ).legacy(v1='v1' in request.GET).as_view(debug)

    @staticmethod
    def create_app(*, debug: bool) -> Bottle:  # noqa: C901
        """
        Create and configure Bottle application with all routes.

        Args:
            debug: Enable debug mode for detailed error pages.

        Returns:
            Configured Bottle application instance with all routes,
            hooks, and error handlers registered.

        """
        app = Bottle()

        @app.hook('before_request')  # type: ignore[untyped-decorator]
        def add_trailing_slash() -> None:
            """Redirect URLs without trailing slash to version with slash."""
            path = request.environ.get('PATH_INFO', '')

            if (
                    path != '/'
                    and not path.endswith('/')
                    and '.' not in path.split('/')[-1]
            ):
                new_url = request.url + '/'
                redirect(new_url, code=301)

        @app.route('/')  # type: ignore[untyped-decorator]
        def session_list() -> str:
            """
            Render session list overview page.

            Returns:
                Rendered HTML template.

            """
            return SessionListView().legacy(
                v1='v1' in request.GET,
            ).as_view(debug)

        @app.route('/styleguide/')  # type: ignore[untyped-decorator]
        def styleguide() -> str:
            """
            Render the design-token and component styleguide.

            Returns:
                Rendered HTML template.

            """
            return StyleguideView().as_view(debug)

        @app.route('/styleguide/v2/')  # type: ignore[untyped-decorator]
        def design_styleguide() -> str:
            """
            Render the V2 design system: theme values and contrasts.

            Returns:
                Rendered HTML template.

            """
            return DesignStyleguideView().as_view(debug)

        @app.route('/algorithm/<algorithm>/')  # type: ignore[untyped-decorator]
        def algorithm_detail(algorithm: str) -> str:
            """
            Render algorithm detail page with variations.

            Returns:
                Rendered HTML template.

            """
            return AlgorithmDetailView(
                algorithm,
                request.GET.o,
            ).legacy(v1='v1' in request.GET).as_view(debug)

        @app.route('/scramble/')  # type: ignore[untyped-decorator]
        def scramble_home() -> str:
            """
            Render the scramble series form, or redirect to its first one.

            Returns:
                Rendered HTML template.

            """
            return ScrambleHomeView(
                request.GET.c,
                request.GET.seed,
            ).legacy(v1='v1' in request.GET).as_view(debug)

        @app.route('/scramble/<cube:int>/<seed>/<index:int>/')  # type: ignore[untyped-decorator]
        def scramble_detail(cube: int, seed: str, index: int) -> str:
            """
            Render one scramble of a seeded series.

            Returns:
                Rendered HTML template.

            """
            parts = request.urlparts
            return ScrambleDetailView(
                cube, seed, index,
                origin=f'{ parts.scheme }://{ parts.netloc }',
            ).legacy(v1='v1' in request.GET).as_view(debug)

        @app.route('/cube/render/')  # type: ignore[untyped-decorator]
        def cube_debug() -> str:
            """
            Render cube rendering tool page with live rotation.

            Returns:
                Rendered HTML template.

            """
            return CubeRenderView(
                orientation=request.GET.o,
                mode=request.GET.m,
                cube_size=request.GET.c,
                palette=request.GET.p,
                algorithm=request.GET.algorithm,
            ).legacy(v1='v1' in request.GET).as_view(debug)

        @app.route('/cube/')  # type: ignore[untyped-decorator]
        def cube_image() -> str:
            """
            Render cube SVG image.

            Returns:
                Rendered SVG image.

            """
            return CubeImageView(
                request.GET.cube_size or request.GET.c,
                request.GET.algo,
                request.GET.case,
                request.GET.mode or request.GET.m,
                request.GET.layout or request.GET.l,
                request.GET.orientation or request.GET.o,
                request.GET.mask,
                request.GET.palette or request.GET.p,
                request.GET.image_size or request.GET.s,
                request.GET.rotation,
                request.GET.distance,
                request.GET.arrows,
            ).as_view(debug)

        Server.add_academy_routes(app, debug=debug)
        Server.add_daily_routes(app, debug=debug)
        Server.add_training_routes(app, debug=debug)

        @app.route('/<cube:int>/<session:path>/<solve:int>/flag/',
                   method='POST')  # type: ignore[untyped-decorator]
        def solve_update_flag(cube: int, session: str, solve: int) -> None:
            """Handle solve update flag POST request."""
            SolveUpdateFlagView(
                cube, session, solve,
                request.POST.flag,
            )

        @app.route('/<cube:int>/<session:path>/<solve:int>/comment/',
                   method='POST')  # type: ignore[untyped-decorator]
        def solve_update_comment(cube: int, session: str, solve: int) -> None:
            """Handle solve update comment POST request."""
            SolveUpdateCommentView(
                cube, session, solve,
                request.POST.comment,
            )

        @app.route('/<cube:int>/<session:path>/<solve:int>/delete/',
                   method='POST')  # type: ignore[untyped-decorator]
        def solve_delete(cube: int, session: str, solve: int) -> None:
            """Handle solve delete POST request."""
            SolveDeleteView(
                cube, session, solve,
            )

        @app.route('/<cube:int>/<session:path>/<solve:int>/')  # type: ignore[untyped-decorator]
        def solve_detail(cube: int, session: str, solve: int) -> str:
            """
            Render solve detail page with analysis.

            Returns:
                Rendered HTML template.

            """
            return SolveDetailView(
                cube, session, solve,
                request.GET.m,
                request.GET.o or 'auto',
            ).legacy(v1='v1' in request.GET).as_view(debug)

        @app.route('/<cube:int>/<session:path>/')  # type: ignore[untyped-decorator]
        def session_detail(cube: int, session: str) -> str:
            """
            Render session detail page with statistics.

            Returns:
                Rendered HTML template.

            """
            return SessionDetailView(
                cube, session,
                request.GET.m,
                request.GET.step,
                request.GET.case_uid,
            ).legacy(
                v1='v1' in request.GET,
            ).listing(
                all_solves=request.GET.solves == 'all',
            ).as_view(debug)

        @app.route('/static/<filepath:path>')  # type: ignore[untyped-decorator]
        def static_serve(filepath: str) -> HTTPResponse:
            """
            Serve static files.

            Returns:
                Static file response.

            """
            return static_file(filepath, root=STATIC_DIRECTORY)

        @app.error(404)  # type: ignore[untyped-decorator]
        def error_404(error: HTTPError) -> str:
            """
            Handle 404 Not Found errors.

            Returns:
                Rendered error page HTML.

            """
            return Error404View(error, request.path).legacy(
                v1='v1' in request.GET,
            ).as_view(debug)

        @app.error(500)  # type: ignore[untyped-decorator]
        def error_500(error: HTTPError) -> str:
            """
            Handle 500 Internal Server errors.

            Returns:
                Rendered error page HTML.

            """
            return Error500View(error, request.path).legacy(
                v1='v1' in request.GET,
            ).as_view(debug)

        return app
