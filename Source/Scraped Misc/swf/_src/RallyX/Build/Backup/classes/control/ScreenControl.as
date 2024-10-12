package classes.control {
	
	import flash.display.Sprite;
	import classes.events.ScreenEvent;
	import classes.screens.ScreenBase;
	import classes.screens.SplashScreen;
	import classes.screens.InstructionScreen;
	import classes.screens.ScoresScreen;
	import classes.screens.GameScreen;
	import flash.display.MovieClip;
	import classes.screens.AnimationScreen;
	import com.greensock.TweenMax;
	
	public class ScreenControl extends Sprite{
	
		// Private Properties
		private var _currScreenID:int;
		private var _nextScreenID:int;
		private var _loadingScreen:MovieClip;
		private var _animationScreen:ScreenBase;
		private var _currScreen:ScreenBase;
		private var _splashScreen:SplashScreen;
		private var _instructionScreen:InstructionScreen;
		private var _scoresScreen:ScoresScreen;
		private var _gameScreen:GameScreen;

		// Constructor
		public function ScreenControl() {
		}
		
		// Public Methods
		public function init():void{
			_loadingScreen = new MovieClip();
			
			_splashScreen = new SplashScreen();
			_splashScreen.addEventListener(ScreenEvent.INITIALIZED, onScreenInit);
			_splashScreen.addEventListener(ScreenEvent.PLAY_CLICK, onPlayClick);
			_splashScreen.addEventListener(ScreenEvent.INSTRUCTIONS_CLICK, onInstructionClick);
			_splashScreen.addEventListener(ScreenEvent.SCORES_CLICK, onScoreClick);
			
			_instructionScreen = new InstructionScreen();
			_instructionScreen.addEventListener(ScreenEvent.INITIALIZED, onScreenInit);
			_instructionScreen.addEventListener(ScreenEvent.PLAY_CLICK, onPlayClick);
			_instructionScreen.addEventListener(ScreenEvent.SCORES_CLICK, onScoreClick);
			
			_scoresScreen = new ScoresScreen();
			_scoresScreen.addEventListener(ScreenEvent.INITIALIZED, onScreenInit);
			_scoresScreen.addEventListener(ScreenEvent.PLAY_CLICK, onPlayClick);
			_scoresScreen.addEventListener(ScreenEvent.INSTRUCTIONS_CLICK, onInstructionClick);
			
			_animationScreen = new AnimationScreen();
			_animationScreen.addEventListener(ScreenEvent.INITIALIZED, onScreenInit);
			_animationScreen.addEventListener(ScreenEvent.ANIMATION_COMPLETE, onAnimationDone);
			
			_gameScreen = new GameScreen();
			_gameScreen.addEventListener(ScreenEvent.INITIALIZED, onScreenInit);
			_gameScreen.addEventListener(ScreenEvent.GAME_OVER, onGameOver);
			
			_currScreenID = 0;
			_currScreen = _splashScreen;
			addChild (_currScreen);
			_currScreen.startShow();
			onPlayClick(new ScreenEvent(ScreenEvent.PLAY_CLICK));
		}
		
		// Private Methods
		private function onGameOver(e:ScreenEvent):void{
			_nextScreenID = 5;
			transitionOut();
		}
		
		private function onAnimationDone(e:ScreenEvent):void{
			_nextScreenID = 4;
			transitionOut();
		}
		
		private function onPlayClick(e:ScreenEvent):void{
			_nextScreenID = 3
			transitionOut();
		}
		
		private function onScoreClick(e:ScreenEvent):void{
			_nextScreenID=2;
			transitionOut();
		}
		
		private function onInstructionClick(e:ScreenEvent):void{
			_nextScreenID=1;
			transitionOut();
		}
		
		private function transitionOut():void{
			TweenMax.to(_currScreen, 0.5, {alpha:0, onComplete:onTransitionOut});
		}
		
		private function onTransitionOut():void{
			removeChild (_currScreen);
			_currScreen.reset();
			if (_nextScreenID == 1){
				_currScreen = _instructionScreen;
			}else if (_nextScreenID == 2){
				_currScreen = _scoresScreen;
			}else if (_nextScreenID == 3){
				_currScreen = _animationScreen;
			}else if (_nextScreenID == 4){
				_currScreen = _gameScreen;
			}else {
				_currScreen = _splashScreen;
			}
			_currScreen.alpha = 0;
			addChild (_loadingScreen);
			_currScreen.init();
		}
		
		private function onScreenInit(e:ScreenEvent):void{
			removeChild(_loadingScreen);
			addChild(_currScreen);
			transitionIn();
		}
		
		private function transitionIn():void{
			TweenMax.to(_currScreen, 0.5, {alpha:1, onComplete:onTransitionIn});
		}
		
		private function onTransitionIn():void{
			_currScreen.startShow();
		}
		

	}// Class
}// Package