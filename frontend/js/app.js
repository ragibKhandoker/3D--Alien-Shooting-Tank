(function () {
  'use strict';

  angular.module('tankApp', ['ngRoute'])

    // Same origin as Flask by default; change if the frontend is hosted elsewhere
    .constant('API_URL', '/api')

    // ---------- Routes ----------
    .config(['$routeProvider', '$httpProvider', function ($routeProvider, $httpProvider) {
      var requireLogin = ['$location', 'AuthService', function ($location, Auth) {
        if (!Auth.isLoggedIn()) { $location.path('/login'); }
      }];
      var guestOnly = ['$location', 'AuthService', function ($location, Auth) {
        if (Auth.isLoggedIn()) { $location.path('/'); }
      }];

      $routeProvider
        .when('/', {
          templateUrl: 'views/play.html', controller: 'PlayController', controllerAs: 'vm',
          resolve: { auth: requireLogin }
        })
        .when('/login', {
          templateUrl: 'views/login.html', controller: 'LoginController', controllerAs: 'vm',
          resolve: { guest: guestOnly }
        })
        .when('/register', {
          templateUrl: 'views/register.html', controller: 'RegisterController', controllerAs: 'vm',
          resolve: { guest: guestOnly }
        })
        .otherwise('/');

      $httpProvider.interceptors.push('AuthInterceptor');
    }])

    // ---------- Auth: token kept in localStorage ----------
    .factory('AuthService', ['$http', 'API_URL', function ($http, API_URL) {
      var TOKEN_KEY = 'tankToken';
      var USER_KEY = 'tankUser';

      function save(res) {
        localStorage.setItem(TOKEN_KEY, res.data.token);
        localStorage.setItem(USER_KEY, JSON.stringify(res.data.user));
        return res.data.user;
      }

      return {
        token: function () { return localStorage.getItem(TOKEN_KEY); },
        user: function () {
          try { return JSON.parse(localStorage.getItem(USER_KEY)); } catch (e) { return null; }
        },
        isLoggedIn: function () { return !!localStorage.getItem(TOKEN_KEY); },
        register: function (form) {
          return $http.post(API_URL + '/auth/register', {
            username: form.username, email: form.email, password: form.password
          }).then(save);
        },
        login: function (form) {
          return $http.post(API_URL + '/auth/login', form).then(save);
        },
        logout: function () {
          localStorage.removeItem(TOKEN_KEY);
          localStorage.removeItem(USER_KEY);
        }
      };
    }])

    // Adds "Authorization: Bearer <token>" to every API call; logs out on 401
    .factory('AuthInterceptor', ['$q', '$location', '$injector', function ($q, $location, $injector) {
      return {
        request: function (config) {
          var token = localStorage.getItem('tankToken');
          if (token) {
            config.headers = config.headers || {};
            config.headers.Authorization = 'Bearer ' + token;
          }
          return config;
        },
        responseError: function (res) {
          var isAuthCall = res.config && /\/auth\/(login|register)$/.test(res.config.url);
          if (res.status === 401 && !isAuthCall) {
            $injector.get('AuthService').logout();
            $location.path('/login');
          }
          return $q.reject(res);
        }
      };
    }])

    .factory('ApiService', ['$http', 'API_URL', function ($http, API_URL) {
      function data(res) { return res.data; }
      return {
        health:     function ()  { return $http.get(API_URL + '/health').then(data); },
        startGame:  function (difficulty) { return $http.post(API_URL + '/game/start', { difficulty: difficulty }).then(data); },
        stopGame:   function ()  { return $http.post(API_URL + '/game/stop').then(data); },
        gameStatus: function ()  { return $http.get(API_URL + '/game/status').then(data); },
        topScores:  function (n, difficulty) {
          return $http.get(API_URL + '/scores/top', { params: { limit: n || 10, difficulty: difficulty || undefined } }).then(data);
        },
        myScores:   function ()  { return $http.get(API_URL + '/scores/me').then(data); },
        myStats:    function ()  { return $http.get(API_URL + '/scores/me/stats').then(data); }
      };
    }])

    // ---------- Controllers ----------
    .controller('NavController', ['$location', 'AuthService', function ($location, Auth) {
      var nav = this;
      nav.auth = Auth;
      nav.logout = function () {
        Auth.logout();
        $location.path('/login');
      };
    }])

    .controller('LoginController', ['$location', 'AuthService', function ($location, Auth) {
      var vm = this;
      vm.form = {};
      vm.submit = function () {
        vm.busy = true;
        vm.error = '';
        Auth.login(vm.form)
          .then(function () { $location.path('/'); })
          .catch(function (err) { vm.error = errorText(err); })
          .finally(function () { vm.busy = false; });
      };
    }])

    .controller('RegisterController', ['$location', 'AuthService', function ($location, Auth) {
      var vm = this;
      vm.form = {};
      vm.submit = function () {
        vm.error = '';
        if (vm.form.password !== vm.form.confirm) {
          vm.error = 'Passwords do not match';
          return;
        }
        vm.busy = true;
        Auth.register(vm.form)
          .then(function () { $location.path('/'); })
          .catch(function (err) { vm.error = errorText(err); })
          .finally(function () { vm.busy = false; });
      };
    }])

    .controller('PlayController', ['$interval', '$q', '$scope', 'ApiService', 'AuthService',
      function ($interval, $q, $scope, Api, Auth) {
        var vm = this;
        var wasRunning = false;

        vm.user = Auth.user();
        vm.status = { running: false };
        vm.scores = [];
        vm.myScores = [];
        vm.stats = {};
        vm.now = Date.now();
        vm.controlGroups = [
          { title: 'Drive', items: [
            { keys: ['W'], label: 'Accelerate' },
            { keys: ['S'], label: 'Reverse' },
            { keys: ['A', 'D'], label: 'Steer' },
            { keys: ['Space'], label: 'Brake' }
          ] },
          { title: 'Combat', items: [
            { keys: ['F'], label: 'Fire a shell' },
            { keys: ['Click'], label: 'Fire a shell' },
            { keys: ['J'], label: 'Jump over aliens' },
            { keys: ['1'], label: 'Boost' }
          ] },
          { title: 'View', items: [
            { keys: ['G'], label: 'First person' },
            { keys: ['H'], label: 'Third person' },
            { keys: ['←', '→'], label: 'Rotate camera' },
            { keys: ['C'], label: 'Day / night' }
          ] },
          { title: 'Game', items: [
            { keys: ['P', 'Esc'], label: 'Pause / resume' },
            { keys: ['R'], label: 'Restart' },
            { keys: ['M'], label: 'Sound on / off' }
          ] }
        ];

        // threat = how many alien icons light up on the card
        vm.difficulties = [
          { id: 'easy',   label: 'Easy',   hint: 'Few, slow aliens',   threat: 1 },
          { id: 'medium', label: 'Medium', hint: 'Steady alien waves', threat: 2 },
          { id: 'hard',   label: 'Hard',   hint: 'Fast, heavy waves',  threat: 3 }
        ];

        // "m:ss" since the current game started
        vm.elapsed = function () {
          if (!vm.status.started_at) { return ''; }
          var secs = Math.max(0, Math.floor(vm.now / 1000 - vm.status.started_at));
          return Math.floor(secs / 60) + ':' + ('0' + secs % 60).slice(-2);
        };

        // score bar width relative to the player's best
        vm.barWidth = function (score) {
          var best = vm.stats.best || 0;
          return best > 0 ? Math.max(3, Math.round(score / best * 100)) + '%' : '3%';
        };
        vm.difficulty = localStorage.getItem('tankDifficulty') || 'medium';
        vm.boardFilter = '';  // '' = all difficulties

        vm.setDifficulty = function (id) {
          vm.difficulty = id;
          localStorage.setItem('tankDifficulty', id);
        };

        vm.setBoardFilter = function (id) {
          vm.boardFilter = id;
          vm.loadScores();
        };

        vm.isMine = function () { return vm.user && vm.status.user_id === vm.user.id; };

        function showError(err) { vm.error = errorText(err); }

        vm.start = function () {
          vm.busy = true;
          vm.error = '';
          Api.startGame(vm.difficulty)
            .then(refreshStatus)
            .catch(showError)
            .finally(function () { vm.busy = false; });
        };

        vm.stop = function () {
          vm.busy = true;
          Api.stopGame()
            .then(refreshStatus)
            .catch(showError)
            .finally(function () { vm.busy = false; });
        };

        vm.loadScores = function () {
          Api.topScores(10, vm.boardFilter).then(function (rows) { vm.scores = rows; }).catch(angular.noop);
          Api.myScores().then(function (rows) { vm.myScores = rows; }).catch(angular.noop);
          Api.myStats().then(function (s) { vm.stats = s || {}; }).catch(angular.noop);
        };

        function refreshStatus() {
          return Api.gameStatus().then(function (s) {
            if (vm.offline) { vm.offline = false; vm.error = ''; }
            vm.status = s;
            // game window just closed -> reload scores
            if (wasRunning && !s.running) { vm.loadScores(); }
            wasRunning = s.running;
          }, function (err) {
            vm.offline = true;
            return $q.reject(err);
          });
        }

        // Poll game status every 2s; refresh scores while playing
        var poll = $interval(function () {
          refreshStatus().catch(angular.noop);
          if (vm.status.running) { vm.loadScores(); }
        }, 2000);
        // 1s tick for the live game timer
        var tick = $interval(function () { vm.now = Date.now(); }, 1000);
        $scope.$on('$destroy', function () { $interval.cancel(poll); $interval.cancel(tick); });

        Api.health().then(function (h) { vm.health = h; }).catch(showError);
        refreshStatus().catch(angular.noop);
        vm.loadScores();
      }]);

  function errorText(err) {
    if (err && err.data && err.data.error) { return err.data.error; }
    var status = err ? err.status : -1;
    if (status <= 0) {
      return 'Cannot reach the server. Make sure "npm run dev" is still running, then refresh the page.';
    }
    if (status >= 500) {
      return 'Flask backend is not responding (HTTP ' + status + '). Check the [backend] lines in the terminal.';
    }
    return 'Request failed (HTTP ' + status + ').';
  }
})();
