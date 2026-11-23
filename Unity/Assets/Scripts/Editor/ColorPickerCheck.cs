#if UNITY_EDITOR
using System.IO;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.EventSystems;

namespace Sitekick
{
	/// <summary>
	/// Drives the gallery's colour picker the way a finger does: pointer down
	/// inside the square, a drag across it, then a drag along the hue strip --
	/// and checks the Sitekick's body is wearing each colour as it moves.
	///
	/// Writes Logs/color-picker/report.txt.
	/// Batch entry point: -executeMethod Sitekick.ColorPickerCheck.RunFromCommandLine
	/// </summary>
	public static class ColorPickerCheck
	{
		const string ScenePath = "Assets/Scenes/ChipGallery.unity";
		const string PhaseKey = "Sitekick.ColorPickerCheck.phase";
		const string LogDir = "Logs/color-picker";

		static int retries;

		[InitializeOnLoadMethod]
		static void Hook()
		{
			EditorApplication.update -= Tick;
			if ( SessionState.GetInt( PhaseKey, 0 ) > 0 )
				EditorApplication.update += Tick;
		}

		public static void RunFromCommandLine()
		{
			Application.runInBackground = true;
			SessionState.SetInt( PhaseKey, 1 );
			AssetDatabase.Refresh();
			EditorSceneManager.OpenScene( ScenePath, OpenSceneMode.Single );
			EditorApplication.update -= Tick;
			EditorApplication.update += Tick;
		}

		static void Tick()
		{
			if ( SessionState.GetInt( PhaseKey, 0 ) != 1 )
				return;

			if ( EditorUtility.scriptCompilationFailed )
			{
				Debug.Log( "ColorPickerCheck: scripts have compile errors" );
				Finish();
			}
			else if ( EditorApplication.isPlaying )
				Run();
			else if ( !EditorApplication.isPlayingOrWillChangePlaymode )
				EditorApplication.isPlaying = true;
		}

		static void Run()
		{
			var picker = Object.FindFirstObjectByType<ColorPicker>();
			if ( picker == null || picker.Area == null || picker.HueBar == null )
			{
				if ( retries++ < 20 )
					return;

				Report( "picker: MISSING" );
				Finish();
				return;
			}

			var report = new StringBuilder();
			report.AppendLine( "picker: " + picker.name );
			report.AppendLine( "areas: square " + picker.Area.rect.size + "  hue " + picker.HueBar.rect.size );

			var ok = true;
			ok &= Drag( picker, picker.Area, new Vector2( 0.75f, 0.5f ), "square 75 % right", report );
			ok &= Drag( picker, picker.Area, new Vector2( 0.30f, 0.85f ), "square up-left", report );
			ok &= Drag( picker, picker.HueBar, new Vector2( 0.33f, 0.5f ), "hue one third", report );
			ok &= Drag( picker, picker.HueBar, new Vector2( 0.66f, 0.5f ), "hue two thirds", report );

			report.AppendLine( "field follows: " + ( Hex() ?? "-" ) );
			report.AppendLine( "RESULT " + ( ok ? "OK" : "FAIL" ) );
			Report( report.ToString() );
			Finish();
		}

		/// <summary>Presses inside a rect at a fraction of its size, drags there and releases.</summary>
		static bool Drag( ColorPicker picker, RectTransform rect, Vector2 fraction, string name, StringBuilder report )
		{
			var data = new PointerEventData( EventSystem.current );
			data.position = Screen( rect, Vector2.zero );

			picker.OnPointerDown( data );

			data.position = Screen( rect, fraction );
			picker.OnDrag( data );

			var expected = picker.Color;
			var published = SitekickColor.Current;
			var body = BodyTint();
			picker.OnPointerUp( data );

			var match = ( published - expected ).maxColorComponent < 0.01f
				&& ( body - expected ).maxColorComponent < 0.01f
				&& Hex() == ColorUtility.ToHtmlStringRGB( expected );

			report.AppendLine( string.Format(
				"  {0,-16} pick#{1}  published #{2}  body #{3}  {4}", name,
				ColorUtility.ToHtmlStringRGB( expected ),
				ColorUtility.ToHtmlStringRGB( published ),
				ColorUtility.ToHtmlStringRGB( body ),
				match ? "ok" : "MISMATCH" ) );

			return match;
		}

		static Vector2 Screen( RectTransform rect, Vector2 fraction )
		{
			var local = new Vector2( rect.rect.xMin + fraction.x * rect.rect.width,
				rect.rect.yMin + fraction.y * rect.rect.height );
			return RectTransformUtility.WorldToScreenPoint( null, rect.TransformPoint( local ) );
		}

		/// <summary>The tint the Sitekick's body renderer is actually drawing with.</summary>
		static Color BodyTint()
		{
			foreach ( var sitekick in Object.FindObjectsByType<EditorSitekick>( FindObjectsSortMode.None ) )
			{
				foreach ( var renderer in sitekick.GetComponentsInChildren<SpriteRenderer>() )
				{
					if ( renderer.gameObject.name != "Body" )
						continue;

					var block = new MaterialPropertyBlock();
					renderer.GetPropertyBlock( block );
					return block.GetColor( "_Color" );
				}
			}

			return Color.clear;
		}

		/// <summary>What the hex field is showing; the picker keeps it in step.</summary>
		static string Hex()
		{
			var panel = Object.FindFirstObjectByType<ChipColorPanel>();
			return panel != null ? panel.Hex : null;
		}

		static void Report( string text )
		{
			Directory.CreateDirectory( LogDir );
			File.WriteAllText( LogDir + "/report.txt", text + "\n" );
			Debug.Log( text );
		}

		static void Finish()
		{
			SessionState.SetInt( PhaseKey, 0 );
			EditorApplication.update -= Tick;
			EditorApplication.isPlaying = false;
			EditorApplication.delayCall += () => EditorApplication.Exit( 0 );
		}
	}
}
#endif
