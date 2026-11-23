using System;
using System.Collections.Generic;
using UnityEngine;

namespace Sitekick
{
	/// <summary>
	/// Plays a chip's Flash movie as a sprite swap at the SWF frame rate, with the
	/// chip's sounds and its stop() points.
	///
	/// The rebuilt chips 7-16 come from the standalone chip SWFs: one drawing per
	/// stage frame, so swapping the renderer's sprite reproduces the timeline exactly.
	/// Sounds are one-shots keyed to a frame, and `stop()` shows up as a pause frame:
	/// the movie holds there until <see cref="Resume"/>, which is how the original
	/// splits an intro from an outro.  A chip whose root ends on `gotoAndPlay("hover")`
	/// has that idle section baked as a loop range instead of a tail: the movie
	/// repeats it for as long as the effect lives, as the original does.
	/// </summary>
	public class ChipMoviePlayer : MonoBehaviour
	{
		[Serializable]
		public class Cue
		{
			public int frame = 1;
			public AudioClip clip;
		}

		public SpriteRenderer target;
		public Sprite[] frames = Array.Empty<Sprite>();
		public float fps = 12f;

		public List<Cue> sounds = new List<Cue>();
		public List<int> pauses = new List<int>();

		[Tooltip( "Frames of the idle section to repeat, 1-based and inclusive. 0, 0 plays the movie once." )]
		public int loopFrom;
		public int loopTo;

		[Tooltip( "How long to hold at a stop() before carrying on by itself. 0 holds until Resume()." )]
		public float pauseSeconds;

		public AudioSource audioSource;

		/// <summary>Raised when the movie reaches a stop() and holds there.</summary>
		public event Action<int> Paused;

		/// <summary>Raised when a sound cue fires, with its 1-based frame.</summary>
		public event Action<int> CueFired;

		/// <summary>Raised when the last frame has been shown.</summary>
		public event Action Finished;

		protected float elapsed;
		protected int shown;
		protected int played;   // frames shown since Restart, counting repeats of the loop
		protected bool paused;
		protected bool started;
		protected bool done;
		protected float held;

		public bool IsPaused => paused;
		public bool IsDone => done;
		public int Frame => shown;

		protected void OnEnable()
		{
			Restart();
		}

		protected void OnDisable()
		{
			paused = false;
		}

		/// <summary>Start again from frame one. A stop() on the first frame is skipped: play() overrides it in Flash.</summary>
		public void Restart()
		{
			elapsed = 0f;
			shown = -1;
			played = 0;
			paused = false;
			done = false;
			held = 0f;
			started = true;
			Show( 0 );
		}

		/// <summary>Carry on after a stop().</summary>
		public void Resume()
		{
			if ( done )
				return;

			paused = false;
			held = 0f;
		}

		/// <summary>Jump to a frame, for tools and tests. Does not run the clock.</summary>
		public void SetFrame( int frame )
		{
			if ( frames == null || frames.Length == 0 )
				return;

			shown = Mathf.Clamp( frame, 0, frames.Length - 1 );
			played = shown;
			Apply();
		}

		protected void Update()
		{
			if ( !started )
			{
				Restart();
				return;
			}

			if ( done || paused )
			{
				if ( paused && pauseSeconds > 0f )
				{
					held += Time.deltaTime;
					if ( held >= pauseSeconds )
						Resume();
				}
				return;
			}

			if ( frames == null || frames.Length == 0 || fps <= 0f )
				return;

			elapsed += Time.deltaTime;
			var next = Mathf.FloorToInt( elapsed * fps );

			// counted apart from `shown`: a looping movie's index wraps, so it can
			// never be compared against the clock
			while ( next > played && !done )
			{
				played++;
				Show( played );
				if ( done )
					break;
			}
		}

		protected void Show( int frame )
		{
			if ( frames == null || frames.Length == 0 )
				return;

			var index = Wrap( frame );

			if ( index >= frames.Length )
			{
				shown = frames.Length - 1;
				Apply();
				done = true;
				Finished?.Invoke();
				return;
			}

			shown = index;
			Apply();
			PlayCue( index + 1 );

			// a stop() on the very first frame is just the movie's idle pose
			if ( index > 0 && pauses != null && pauses.Contains( index + 1 ) )
			{
				paused = true;
				held = 0f;
				Paused?.Invoke( index + 1 );
			}
		}

		/// <summary>
		/// Fold a playhead past the idle loop back onto its first frame.  Flash ends
		/// these movies on a `gotoAndPlay("hover")`, so the frames after that jump --
		/// the retract -- are never shown while the chip is on the Sitekick, and the
		/// idle section repeats for as long as the effect lives instead.
		/// </summary>
		protected int Wrap( int frame )
		{
			if ( frames == null || frames.Length == 0 || loopFrom < 1 || loopTo < loopFrom )
				return frame;

			var from = loopFrom - 1;
			var to = Mathf.Min( loopTo - 1, frames.Length - 1 );
			if ( to <= from || frame <= to )
				return frame;

			return from + ( frame - from ) % ( to - from + 1 );
		}

		protected void Apply()
		{
			if ( target != null && frames != null && shown >= 0 && shown < frames.Length )
				target.sprite = frames[ shown ];
		}

		protected void PlayCue( int frame )
		{
			if ( sounds == null || audioSource == null )
				return;

			for ( int i = 0; i < sounds.Count; i++ )
			{
				var cue = sounds[ i ];
				if ( cue != null && cue.clip != null && cue.frame == frame )
				{
					audioSource.PlayOneShot( cue.clip );
					CueFired?.Invoke( cue.frame );
				}
			}
		}
	}
}
